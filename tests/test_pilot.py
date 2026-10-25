"""Offline policy/acquisition/QA tests. No Colab, embeddings, external sockets or LLMs."""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from law_crawler.pilot import PilotClient,Response,RobotsPolicy,check_url,acquire,original_filename
from law_crawler.catalog import candidate_from_page,validate_catalog
from law_crawler.quality import assess
from law_crawler.manual_inbox import scan
from preprocess.legal_parser import hierarchy,Block,extract
from preprocess.offline_ingestion import initialize,ingest,load_stage,review
from batch.contracts import canonical,digest

HOST='vanban.chinhphu.vn'
URL='https://vanban.chinhphu.vn/legal-test.txt'
TEXT='SYNTHETIC TEST ONLY\nĐiều 1. Thử nghiệm\n1. Khoản giả lập.\na) Điểm giả lập.\nĐiều 2. Tiếp theo\n'


class Clock:
    def __init__(self):self.now=0;self.waits=[]
    def __call__(self):return self.now
    def sleep(self,seconds):self.waits.append(seconds);self.now+=seconds


def client(tmp_path,responses):
    clock=Clock(); calls=[];responses=iter(responses)
    def send(url):calls.append((url,clock()));return next(responses)
    c=PilotClient(tmp_path/'network',send=send,clock=clock,sleep=clock.sleep)
    c.robots[HOST]=RobotsPolicy('User-agent: *\nAllow: /\nCrawl-delay: 5')
    return c,calls,clock


def policy(url=URL):
    return dict(host=HOST,decision='approved_public_download',permission_evidence='SYNTHETIC permission fixture',approved_urls=[url],min_interval_seconds=3)


@pytest.mark.parametrize('url',['http://vanban.chinhphu.vn/a','https://evil.invalid/a','https://vanban.chinhphu.vn@evil.invalid/a','https://vanban.chinhphu.vn/a?api_key=not-a-key','https://vanban.chinhphu.vn/allowed/../private','https://127.0.0.1/a'])
def test_pilot_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):check_url(url)


def test_robots_longest_match_and_allow_tie():
    r=RobotsPolicy('User-agent: *\nAllow: /\nDisallow: /Pages/\nDisallow: /api/\nAllow: /api/public$')
    assert not r.can_fetch('HanoiLandLawPilot/1.0','https://vbpl.vn/Pages/a')
    assert not r.can_fetch('HanoiLandLawPilot/1.0','https://vbpl.vn/api/private')
    assert r.can_fetch('HanoiLandLawPilot/1.0','https://vbpl.vn/api/public')
    r=RobotsPolicy('User-agent: *\nDisallow: /\nUser-agent: HanoiLandLawPilot\nAllow: /legal\nDisallow: /legal')
    assert r.can_fetch('HanoiLandLawPilot/1.0','https://vbpl.vn/legal')


def test_no_download_without_explicit_permission_and_registered_endpoint(tmp_path):
    c,calls,_=client(tmp_path,[])
    with pytest.raises(ValueError,match='approval'):c.fetch(URL,purpose='document')
    with pytest.raises(ValueError):c.fetch(URL+'x',purpose='document',policy=policy())
    with pytest.raises(ValueError):c.fetch(URL,purpose='policy')
    assert calls==[]


def test_robots_denial_blocks_before_any_connection(tmp_path):
    c,calls,_=client(tmp_path,[])
    c.robots[HOST]=RobotsPolicy('User-agent: *\nDisallow: /legal-test')
    with pytest.raises(ValueError,match='Robots'):c.fetch(URL,purpose='document',policy=policy())
    assert calls==[]


def test_redirect_destination_validated_before_connecting(tmp_path):
    c,calls,_=client(tmp_path,[Response(302,{'location':'https://evil.invalid/x'},b'')])
    with pytest.raises(ValueError):c.fetch(URL)
    assert len(calls)==1


def test_conservative_delay_retry_after_and_retry_cap(tmp_path):
    c,calls,clock=client(tmp_path,[Response(503,{'retry-after':'7'},b'wait'),Response(200,{},b'ok')])
    assert c.fetch(URL)['ok']
    assert calls[1][1]-calls[0][1]>=7
    assert max(clock.waits)>=7
    c,calls,_=client(tmp_path/'cap',[Response(503,{},b'')]*4)
    assert not c.fetch(URL)['ok'] and len(calls)==4  # initial + at most 3 retries
    c,calls,_=client(tmp_path/'delay',[Response(200,{},b'ok')]*2)
    c.fetch(URL);c.fetch(URL)
    assert calls[1][1]-calls[0][1]>=5


@pytest.mark.parametrize('status',[401,403,429])
def test_access_stop_survives_restart_without_retries(tmp_path,status):
    c,calls,_=client(tmp_path,[Response(status,{'retry-after':'100'},b'stop')])
    assert not c.fetch(URL)['ok']
    with pytest.raises(ValueError,match='stopped'):c.fetch(URL)
    next_client=PilotClient(tmp_path/'network',send=lambda *_:pytest.fail('Must not reconnect'))
    with pytest.raises(ValueError,match='stopped'):next_client.fetch(URL)
    assert len(calls)==1


def test_access_challenge_is_never_bypassed(tmp_path):
    c,calls,_=client(tmp_path,[Response(200,{},b'<html>verify you are human</html>')])
    assert c.fetch(URL)['status']=='access_control_detected'
    with pytest.raises(ValueError):c.fetch(URL)
    assert len(calls)==1


def test_metadata_observation_does_not_certify_current_validity():
    html='<table>'+''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k,v in {
        'Số ký hiệu':'SYNTHETIC-1','Trích yếu':'SYNTHETIC luật thử nghiệm','Loại văn bản':'Luật',
        'Cơ quan ban hành':'SYNTHETIC authority','Ngày ban hành':'01-01-2020','Ngày có hiệu lực':'02-01-2020'}.items())+'</table>'
    c=candidate_from_page(URL,html,retrieved_at='2026-01-01T00:00:00+00:00',evidence_sha256=digest(html),topics=['land_law'],expected_number='SYNTHETIC-1')
    assert c['effective_date'] is None and c['legal_validity']=='unknown'
    assert c['effective_date_claim']['date']=='2020-01-02'
    assert c['publication_date'] is None
    assert validate_catalog([c])['discovered']==1
    with pytest.raises(ValueError):validate_catalog([c,c])
    with pytest.raises(ValueError):candidate_from_page(URL,html,retrieved_at='',evidence_sha256=digest(html),topics=[],expected_number='wrong')


def test_acquisition_provenance_deduplication_and_pending_review(tmp_path):
    c,calls,_=client(tmp_path,[Response(200,{'content-type':'text/plain','etag':'synthetic'},TEXT.encode())])
    root=initialize(tmp_path/'corpus')
    candidate=dict(official_identifier='SYNTHETIC-PILOT-TEST',official_number='SYNTHETIC-1',title='SYNTHETIC pilot fixture',
        document_type='synthetic',issuing_authority='SYNTHETIC authority',jurisdiction='VN',source_url=URL,download_urls=[URL])
    result=acquire(c,candidate,policy(),root)
    assert result['review_status']=='pending' and result['legal_validity']=='unknown' and not result['sealed']
    artifact=result['artifacts'][0]
    assert artifact['sha256']==digest(TEXT)
    assert artifact['http']['chain'][0]['headers']['etag']=='synthetic'
    stage=load_stage(root,artifact['stage']['stage_id'])
    assert stage['raw_sha256']==digest(TEXT)
    assert stage['status']=='pending'
    assert acquire(c,candidate,policy(),root)==result and len(calls)==1


def test_instrument_cap_prevents_request_number_41(tmp_path):
    root=initialize(tmp_path/'corpus')
    reservation=root/'acquisitions/reservations';reservation.mkdir(parents=True)
    for i in range(40):(reservation/f'{i:064x}.json').write_text('{}')
    c,calls,_=client(tmp_path,[])
    with pytest.raises(ValueError,match='40-instrument'):acquire(c,{'official_identifier':'SYNTHETIC-41','download_urls':[URL]},policy(),root)
    assert calls==[]


def test_missing_articles_and_hash_corruption_quarantine():
    parsed=hierarchy([Block('Điều 1. A\nĐiều 3. C\n')])
    assert 'missing_article_numbers:2' in assess(parsed)['critical']
    parsed['text_sha256']='0'*64
    assert 'extracted_text_checksum_mismatch' in assess(parsed)['critical']


def test_quality_gate_is_applied_by_existing_ingestion(tmp_path):
    root=initialize(tmp_path/'corpus')
    source=tmp_path/'incomplete.txt';source.write_text('SYNTHETIC incomplete fixture\nĐiều 1. A\nĐiều 3. C\n')
    metadata=dict(file=source.name,official_identifier='SYNTHETIC-INCOMPLETE',official_number='SYNTHETIC-GAP',document_type='test',
        title='SYNTHETIC incomplete',issuing_authority='SYNTHETIC',jurisdiction='VN',source_url='https://synthetic.invalid/test',
        acquired_at='2026-01-01T00:00:00+00:00',is_synthetic=True)
    path=tmp_path/'manifest.json';path.write_text(canonical(metadata))
    result=ingest(root,path)
    assert result['status']=='quarantined'
    with pytest.raises(ValueError):review(root,result['stage_id'],dict(decision='approved',reviewer='SYNTHETIC',reason='test',
        evidence_locator='test',reviewed_at='2026-01-01T00:00:00+00:00'))


def test_actual_registry_and_discovery_evidence_are_consistent():
    root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'corpus/phase-d-candidates.json').read_text())
    assert validate_catalog(data['candidates'])==data['summary']
    policies=json.loads((root/'corpus/source-approvals.json').read_text())
    by_host={s['host']:s for s in policies['sources']}
    assert not any(s['decision']=='approved_public_download' for s in policies['sources'])
    assert policies['approved_for_automated_document_download']==0
    assert all(not c['full_text_acquired'] for c in data['candidates'])
    for candidate in data['candidates']:
        assert candidate['discovery_evidence_sha256']
        assert candidate['legal_validity']=='unknown' and candidate['review_status']=='pending'
        for url in candidate['download_urls']:
            host=urlsplit(url).hostname
            assert host in by_host, host
            assert by_host[host]['decision']!='approved_public_download'
    assert by_host['vbpl.vn']['decision']=='blocked_ambiguous_access_controls'
    assert by_host['datafiles.chinhphu.vn']['robots_http_status']==403
    assert all(c['download_urls'] for c in data['candidates'])
    assert {c['jurisdiction'] for c in data['candidates']}=={'VN','VN-HN'}


def test_hanoi_masthead_fallback_is_marked_as_pending_evidence():
    html=('<div>ỦY BAN NHÂN DÂN THÀNH PHỐ HÀ NỘI</div><table>'
          '<tr><td>Số ký hiệu văn bản</td><td>99/2099/QĐ-UBND</td></tr>'
          '<tr><td>Ngày ban hành</td><td>01/02/2099</td></tr>'
          '<tr><td>Ngày có hiệu lực</td><td>02/02/2099</td></tr>'
          '<tr><td>Loại văn bản</td><td>Quyết định</td></tr>'
          '<tr><td>Trích yếu</td><td>SYNTHETIC Hà Nội test</td></tr></table>')
    c=candidate_from_page('https://vanban.hanoi.gov.vn/synthetic',html,retrieved_at='2026-01-01T00:00:00+00:00',
        evidence_sha256=digest(html),topics=['hanoi_implementation'],expected_number='99/2099/QĐ-UBND')
    assert c['issuing_authority']=='UBND Thành phố Hà Nội'
    assert 'pending human confirmation' in c['issuing_authority_evidence']
    assert c['issuance_date']=='2099-02-01' and c['legal_validity']=='unknown'


def test_original_filename_safety():
    assert original_filename(URL,{'content-disposition':'attachment; filename="original.txt"'})=='original.txt'
    with pytest.raises(ValueError):original_filename(URL,{'content-disposition':'attachment; filename="../outside.pdf"'})


def test_draft_release_is_empty_unsealed_and_idempotent(tmp_path):
    from law_crawler.reporting import prepare
    from preprocess.offline_ingestion import database
    from backend.db.models.legal import CorpusRelease,LegalDocument
    from sqlalchemy import select,func
    root=Path(__file__).resolve().parents[1]
    registry=root/'corpus/phase-d-candidates.json'; policies=root/'corpus/source-approvals.json'
    first=prepare(registry,policies,tmp_path/'corpus')
    assert prepare(registry,policies,tmp_path/'corpus')==first
    assert first['downloaded_instruments']==0 and first['chunks']==0 and first['reviewed']==0
    with database(tmp_path/'corpus') as factory,factory() as session:
        release=session.scalar(select(CorpusRelease))
        assert release.published_at is None and release.manifest_sha256 is None and not release.is_synthetic
        assert session.scalar(select(func.count()).select_from(LegalDocument))==0


def test_container_headings_require_standalone_lines():
    # A wrapped cross-reference must not become a new container heading (which would detach
    # later clauses from their article and quarantine a valid document).
    parsed=hierarchy([Block('Chương I\nĐiều 1. A\n1. Nội dung\nMục 5 Chương III của Nghị định này.\n2. Tiếp\n')])
    assert sum(n['kind']=='article' for n in parsed['nodes'])==1
    assert 'section:5' not in {n['locator'] for n in parsed['nodes']}


def test_wrapped_article_cross_reference_is_not_a_heading():
    parsed=hierarchy([Block('Điều 1. A\n1. Nội dung\nĐiều 2. B\nĐiều 2 của Luật này quy định.\n')])
    assert sum(n['kind']=='article' for n in parsed['nodes'])==2


def _pdf_with(pages, path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer=PdfWriter()
    for text in pages:
        page=writer.add_blank_page(width=612,height=792)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        stream=DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 50 740 Td ('+text.encode()+b') Tj ET')
        page[NameObject('/Contents')]=writer._add_object(stream)
    writer.write(path); return path


def test_trailing_nontext_pdf_page_is_tolerated_but_interior_is_not(tmp_path):
    blocks,warnings=extract(_pdf_with(['Dieu 1. Noi dung',''],tmp_path/'trailing.pdf'))
    assert any('Trailing non-text' in w for w in warnings)
    with pytest.raises(Exception):
        extract(_pdf_with(['Dieu 1. Noi dung','','Dieu 2. Tiep'],tmp_path/'interior.pdf'))
    with pytest.raises(Exception):
        extract(_pdf_with([''],tmp_path/'blank.pdf'))


def _manual_candidate(number, identifier):
    return dict(official_identifier=identifier,official_number=number,document_type='Quyết định',
        title='Quy định thử nghiệm',issuing_authority='UBND Thành phố Hà Nội',jurisdiction='VN-HN',
        issuance_date=None,publication_date=None,source_url=URL,download_urls=[],topics=['hanoi_implementation'],
        legal_validity='unknown',review_status='pending',discovery_evidence_sha256='0'*64)


def test_manual_inbox_scan_matches_rejects_ambiguity_and_dedups(tmp_path):
    root=initialize(tmp_path/'ws')
    ids={'A':'VN-HN:UBND Thành phố Hà Nội:12/2099/QĐ-UBND','B':'VN-HN:UBND Thành phố Hà Nội:13/2099/QĐ-UBND',
         'C':'VN-HN:UBND Thành phố Hà Nội:14/2099/QĐ-UBND','D':'VN-HN:UBND Thành phố Hà Nội:15/2099/QĐ-UBND'}
    numbers={'A':'12/2099/QĐ-UBND','B':'13/2099/QĐ-UBND','C':'14/2099/QĐ-UBND','D':'15/2099/QĐ-UBND'}
    registry=tmp_path/'registry.json'
    registry.write_text(canonical(dict(schema_version=2,candidates=[_manual_candidate(numbers[k],ids[k]) for k in ids])))
    body=('12/2099/QĐ-UBND\nĐiều 1. A\nĐiều 2. B\n').encode()
    def put(key,name,data):
        folder=root/'manual-inbox'/digest(ids[key]); folder.mkdir(parents=True,exist_ok=True); (folder/name).write_bytes(data)
    put('A','12.txt',body)
    put('B','13.txt',body)                      # identical bytes -> duplicate
    put('C','14.txt',b'no document number here\n')
    put('D','a.txt',body); put('D','b.txt',b'other')   # ambiguous
    (root/'manual-inbox'/'deadbeef').mkdir(); (root/'manual-inbox'/'deadbeef'/'x.txt').write_bytes(b'x')
    report=scan([registry],root,ingest_files=True)
    assert [m['official_number'] for m in report['matched']]==['12/2099/QĐ-UBND']
    assert report['ingested'][0]['stage']['status']=='pending'
    assert len(report['duplicates'])==1 and len(report['unconfirmed'])==1
    assert len(report['ambiguous'])==1 and len(report['unmatched'])==1
    assert (root/'manual-inbox'/digest(ids['A'])/'12.txt').read_bytes()==body
    assert (root/'manual-inbox'/digest(ids['A'])/'acquisition.json').is_file()


def test_phase_d1_registry_and_policy_are_consistent():
    root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'corpus/phase-d1-instruments.json').read_text())
    assert validate_catalog(data['candidates'])['discovered']==8
    policies=json.loads((root/'corpus/phase-d1-source-approvals.json').read_text())
    approved={s['host']:s for s in policies['sources'] if s['decision']=='approved_public_download'}
    assert set(approved)=={'congbaocdn.chinhphu.vn'}
    urls={u for c in data['candidates'] for u in c['download_urls']}
    assert urls==set(approved['congbaocdn.chinhphu.vn']['approved_urls'])
    assert approved['congbaocdn.chinhphu.vn']['robots_http_status']==404
    assert all(c['legal_validity']=='unknown' and not c['full_text_acquired'] for c in data['candidates'])
    base=json.loads((root/'corpus/source-approvals.json').read_text())
    assert base['approved_for_automated_document_download']==0
