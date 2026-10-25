"""Narrow destructive-operation guard shared by legacy indexing entrypoints."""


def prepare_collection(client, collection_name, *, recreate=False, confirm_collection=None):
    if not collection_name or collection_name.strip() != collection_name:
        raise ValueError("An exact, nonempty collection name is required")
    if not client.collection_exists(collection_name=collection_name):
        return
    if not recreate or confirm_collection != f"DELETE:{collection_name}":
        raise ValueError(
            "Collection exists; recreation requires --recreate and "
            "--confirm-collection DELETE:<exact-name>"
        )
    client.delete_collection(collection_name=collection_name)


def destructive_cli_args():
    import argparse
    parser = argparse.ArgumentParser(description="Legacy indexing (destructive recreation is opt-in)")
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--confirm-collection")
    return vars(parser.parse_args())
