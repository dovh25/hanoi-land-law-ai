# Use the latest Node version automatically
FROM node:22.21.1-alpine3.22

WORKDIR /app/frontend

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm ci

# Copy the rest of the code
COPY . .

# Run the app
# --host is CRITICAL for Vite to work inside Docker
CMD ["npm", "run", "dev", "--", "--host"]
