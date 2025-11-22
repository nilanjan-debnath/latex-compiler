from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.core.config import settings
from app.core.ratelimiter import limiter
from app.core.logger import logger, LoggingMiddleware
from app.compiler.v1.services import compile_tex_to_pdf
from app.compiler.v1.controllers import router as compiler_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    # setup ratelimiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiter setup complete.")

    # Yield control to the application
    yield

    # --- Shutdown ---
    logger.info("Shutting down...")


# Initialize the FastAPI app with the lifespan manager
app = FastAPI(
    title="Latex Compiler",
    docs_url=None if settings.env == "prod" else "/docs",
    redoc_url=None if settings.env == "prod" else "/redoc",
    openapi_url=None if settings.env == "prod" else "/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=settings.origins.split(" "),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add Logging middleware
app.add_middleware(LoggingMiddleware)


app.include_router(compiler_v1_router)


@limiter.limit(settings.ratelimit_guest)
@app.get("/", status_code=status.HTTP_200_OK)
async def root(request: Request):
    logger.info("logging message from root endpoint")
    return {"message": f"Latex-Compiler is running on {settings.env} Environment"}


@limiter.limit(settings.ratelimit_guest)
@app.get(path="/healthz", status_code=status.HTTP_200_OK)
async def health_check(request: Request):
    tex_path = "uploads/health_check.tex"
    _result_path, success = await compile_tex_to_pdf(tex_path)
    if not success:
        return {"status": "error"}
    return {"status": "ok"}
