#!/bin/bash

# Script to run docker-compose locally for the LOTR SUT project

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting LOTR SUT Docker Compose Stack...${NC}"

# Check if docker and docker-compose are installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

# Navigate to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../" && pwd)"
cd "$PROJECT_ROOT"

# Load environment variables if .env exists
if [ -f .env ]; then
    echo -e "${BLUE}Loading environment variables from .env${NC}"
    export $(cat .env | grep -v '#' | xargs)
fi

# Build and start services
echo -e "${BLUE}Building and starting services...${NC}"
docker-compose up --build -d

# Wait for services to be healthy
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 10

# Check service health
echo -e "${BLUE}Checking service health...${NC}"
docker-compose ps

echo -e "${GREEN}LOTR SUT stack is running!${NC}"
echo -e "${GREEN}Frontend: http://localhost:3000${NC}"
echo -e "${GREEN}Backend: http://localhost:5000${NC}"
echo -e "${GREEN}Caddy: http://localhost${NC}"