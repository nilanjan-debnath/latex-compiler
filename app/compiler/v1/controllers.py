import os
from fastapi import APIRouter, Request, BackgroundTasks, status, HTTPException
from fastapi.responses import FileResponse
from fastapi import UploadFile
from app.compiler.v1.services import create_tex_file, compile_tex_to_pdf, clean_files
from app.core.ratelimiter import limiter
from app.core.config import settings

router = APIRouter(prefix="/v1/compiler", tags=["compiler", "v1"])


@limiter.limit(settings.ratelimit_guest)
@router.post("/tex_file/")
async def create_upload_file(
    request: Request, background_tasks: BackgroundTasks, file: UploadFile
):
    try:
        tex_content = await file.read()
        tex_path = await create_tex_file(tex_content, file.filename)
        result_path, success = await compile_tex_to_pdf(tex_path)

        background_tasks.add_task(clean_files, tex_path)

        if success:
            return FileResponse(
                result_path,
                media_type="application/pdf",
                filename=os.path.basename(result_path),
            )
        else:
            return FileResponse(
                result_path,
                media_type="text/plain",
                filename="error.log",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
    except HTTPException as e:
        if tex_path:
            clean_files(tex_path)
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server Error: {str(e)}",
        )


# FIXME: not possible for multiline text input not support in fastapi directly
# @router.post("/tex_content/")
async def compile_tex_content(
    request: Request, background_tasks: BackgroundTasks, content: str
):
    try:
        tex_path = await create_tex_file(content, None)
        result_path, success = await compile_tex_to_pdf(tex_path)

        background_tasks.add_task(clean_files, tex_path)

        if success:
            return FileResponse(
                result_path,
                media_type="application/pdf",
                filename="compiled_content.pdf",
            )
        else:
            return FileResponse(
                result_path,
                media_type="text/plain",
                filename="error.log",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
    except HTTPException as e:
        if tex_path:
            clean_files(tex_path)
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server Error: {str(e)}",
        )
