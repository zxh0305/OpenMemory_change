# Contributing to OpenMemory

We are a team of developers passionate about the future of AI and open-source software. With years of experience in both fields, we believe in the power of community-driven development and are excited to build tools that make AI more accessible and personalized.

## Ways to Contribute

We welcome all forms of contributions:
- Bug reports and feature requests through GitHub Issues
- Documentation improvements
- Code contributions
- Testing and feedback
- Community support and discussions

## Development Workflow

1. Fork the repository
2. Create your feature branch (`git checkout -b openmemory/feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin openmemory/feature/amazing-feature`)
5. Open a Pull Request

## Development Setup

### Backend Setup

```bash
# 1. 创建环境变量文件
# 在 api/ 目录下创建 .env 文件，设置 OPENAI_API_KEY 和其他配置
# 参考 api/.env.example

# 2. 构建容器
docker compose build

# 3. 启动服务
docker compose up -d
```

### Frontend Setup

The frontend is a React application. To start the frontend:

```bash
# 1. 创建环境变量文件
# 在 ui/ 目录下创建 .env 文件
# 参考 ui/.env.example

# 2. 安装依赖并启动开发服务器（本地开发）
cd ui
pnpm install
pnpm dev
```

或者使用 Docker Compose（推荐）：

```bash
# 使用 docker compose 启动所有服务（包括前端）
docker compose up -d
```

### Prerequisites
- Docker and Docker Compose
- Python 3.9+ (for backend development)
- Node.js (for frontend development)
- OpenAI API Key (for LLM interactions)

### Getting Started
Follow the setup instructions in the README.md file to set up your development environment.

## Code Standards

We value:
- Clean, well-documented code
- Thoughtful discussions about features and improvements
- Respectful and constructive feedback
- A welcoming environment for all contributors

## Pull Request Process

1. Ensure your code follows the project's coding standards
2. Update documentation as needed
3. Include tests for new features
4. Make sure all tests pass before submitting

Join us in building the future of AI memory management! Your contributions help make OpenMemory better for everyone.
