import os
import uuid
import asyncio
import aiofiles
from pathlib import Path
from app.core.logger import logger

UPLOAD_DIRECTORY = Path(__file__).parent.parent.parent.parent / "uploads"
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)


async def create_tex_file(content: bytes | str, filename: str | None) -> str:
    filename = filename or f"{uuid.uuid4()}.tex"
    file_path = os.path.join(UPLOAD_DIRECTORY, filename)

    mode = "wb" if isinstance(content, bytes) else "w"
    async with aiofiles.open(file_path, mode) as f:
        await f.write(content)

    logger.info(f"Saved source file at: {file_path}")
    return file_path


async def compile_tex_to_pdf(tex_file_path: str) -> tuple[str, bool]:
    """Compile a .tex file into a .pdf using latexmk asynchronously."""
    if not tex_file_path or not os.path.exists(tex_file_path):
        logger.error(f"tex_file_path is invalid or does not exist: {tex_file_path}")
        raise FileNotFoundError(f"TEX file not found: {tex_file_path}")

    # Convert to absolute paths
    tex_file_path = os.path.abspath(tex_file_path)
    output_dir = os.path.dirname(tex_file_path)

    pdf_path = tex_file_path.rsplit(".tex", 1)[0] + ".pdf"
    log_path = tex_file_path.rsplit(".tex", 1)[0] + ".log"

    cmd = [
        "latexmk",
        "-pdf",
        "-interaction=nonstopmode",
        f"-output-directory={output_dir}",
        tex_file_path,  # Full absolute path
    ]

    try:
        # No cwd - use absolute paths instead
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0 and os.path.exists(pdf_path):
            logger.info(f"Compilation successful: {pdf_path}")
            return pdf_path, True
        else:
            logger.error(f"Compilation failed for {tex_file_path}")
            if stderr:
                logger.warning(f"latexmk stderr: {stderr.decode(errors='replace')}")

            if not os.path.exists(log_path):
                async with aiofiles.open(log_path, "wb") as f:
                    await f.write(stderr + stdout)

            return log_path, False

    except Exception as e:
        logger.warning(f"Exception compiling {tex_file_path}: {e}")
        raise


def clean_files(tex_path: str, with_tex: bool = True) -> None:
    """Remove LaTeX intermediate files."""
    base = tex_path.rsplit(".tex", 1)[0] if tex_path.endswith(".tex") else tex_path
    extensions = (
        ".aux",
        ".log",
        ".out",
        ".fls",
        ".fdb_latexmk",
        ".pdf",
        ".toc",
        ".lof",
        ".lot",
        ".synctex.gz",
    )
    if with_tex:
        extensions += (".tex",)
    for ext in extensions:
        file_path = base + ext
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Removed: {file_path}")
    logger.debug(f"Cleaned up files for base: {base}")
