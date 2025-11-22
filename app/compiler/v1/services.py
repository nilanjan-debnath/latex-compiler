import os
import glob
import uuid
import asyncio
import aiofiles
from app.core.logger import logger

UPLOAD_DIRECTORY = "uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)


async def create_tex_file(content: bytes | str, filename: str | None) -> str:
    filename = filename or f"{uuid.uuid4()}.tex"
    file_path = os.path.join(UPLOAD_DIRECTORY, filename)

    mode = "wb" if isinstance(content, bytes) else "w"
    async with aiofiles.open(file_path, mode) as f:
        await f.write(content)

    logger.info(f"Saved source file at: {file_path}")
    return file_path


async def compile_tex_to_pdf(tex_file_path: str) -> tuple[str, bool]:
    """Compile a .tex file into a .pdf using tectonic asynchronously."""
    # Ensure tex_file_path is valid before proceeding
    if not tex_file_path or not os.path.exists(tex_file_path):
        logger.error(f"tex_file_path is invalid or does not exist: {tex_file_path}")
        raise FileNotFoundError(f"TEX file not found: {tex_file_path}")

    output_dir = os.path.dirname(tex_file_path)

    cmd = [
        "tectonic",
        "-X",
        "compile",
        "--keep-logs",
        "--outdir",
        output_dir,
        tex_file_path,
    ]

    try:
        # Run tectonic asynchronously
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # Check if the PDF was actually created
        pdf_path = tex_file_path.replace(".tex", ".pdf")
        log_path = tex_file_path.replace(".tex", ".log")
        if process.returncode == 0 and os.path.exists(pdf_path):
            logger.info(f"Compilation successful: {pdf_path}")
            return pdf_path, True
        else:
            logger.error(f"Compilation failed for {tex_file_path}")
            # Attempt to log stderr if needed, or return the internal log file
            if stderr:
                logger.warning(f"Tectonic Stderr: {stderr.decode()}")

            # If the .log file wasn't generated (rare crash), write the stderr to it
            if not os.path.exists(log_path):
                async with aiofiles.open(log_path, "wb") as f:
                    await f.write(stderr + stdout)

            return log_path, False

    except Exception as e:
        logger.warning(f"Exception compiling {tex_file_path}: {e}")
        raise e


def clean_files(tex_path: str) -> None:
    """Remove LaTeX intermediate files."""
    base = tex_path.rpartition(".")[0].strip()
    for ext in (".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".tex", ".pdf"):
        for file in glob.glob(base + ext):
            os.remove(file)
    logger.debug(f"Cleaned up files for base: {base}")
