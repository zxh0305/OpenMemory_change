# OpenMemory API

This directory contains the backend API for OpenMemory, built with FastAPI and SQLAlchemy. This also runs the Mem0 MCP Server that you can use with MCP clients to remember things.

## Quick Start with Docker (Recommended)

The easiest way to get started is using Docker. Make sure you have Docker and Docker Compose installed.

1. Create `.env` file:
```bash
# 在 api/ 目录下创建 .env 文件
# 参考 api/.env.example，设置 OPENAI_API_KEY 和其他配置
```

2. Build the containers:
```bash
docker compose build
```

3. Start the services:
```bash
docker compose up -d
```

The API will be available at `http://localhost:8765`

### Common Docker Commands

- View logs: `docker compose logs -f`
- View API logs: `docker compose logs -f openmemory-api`
- Open shell in container: `docker compose exec openmemory-api bash`
- Run database migrations: `docker compose exec openmemory-api alembic upgrade head`
- Stop containers: `docker compose down`
- Stop and remove volumes: `docker compose down -v`

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: `http://localhost:8765/docs`
- ReDoc: `http://localhost:8765/redoc`

## Project Structure

- `app/`: Main application code
  - `models.py`: Database models
  - `database.py`: Database configuration
  - `routers/`: API route handlers
- `migrations/`: Database migration files
- `tests/`: Test files
- `alembic/`: Alembic migration configuration
- `main.py`: Application entry point

## Development Guidelines

- Follow PEP 8 style guide
- Use type hints
- Write tests for new features
- Update documentation when making changes
- Run migrations for database changes
