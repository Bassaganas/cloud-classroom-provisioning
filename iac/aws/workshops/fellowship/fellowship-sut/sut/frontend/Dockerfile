FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm install

# Copy source files
COPY . .

# Expose port
EXPOSE 3000

# Start development server
CMD ["npm", "start"]
