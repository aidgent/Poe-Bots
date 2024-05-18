from __future__ import annotations
from typing import AsyncIterable
import os
import sys
import requests
import fastapi_poe as fp
from modal import Image, Stub, asgi_app, Secret, Mount
import time
import io
import logging
from PIL import Image as PILImage
sys.path.append("/path/to/my/local/python3.12/site-packages")
from stegano import lsb

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class StegoBot(fp.PoeBot):
    async def get_response_with_context(
        self, request: fp.QueryRequest, context: fp.RequestContext
    ) -> AsyncIterable[fp.PartialResponse]:
        try:
            start_time = time.time()
            last_message = request.query[-1].content
            logger.debug(f"Received request from {context.http_request.client.host}")
            logger.debug(f"Method: {context.http_request.method}, URL: {context.http_request.url}")
            logger.debug(f"Headers: {context.http_request.headers}")
            logger.debug(f"Query Params: {context.http_request.query_params}")
            logger.debug(f"Last Message: {last_message}")

            if last_message.startswith("/hide"):
                text_to_hide = last_message[5:].strip()
                logger.debug(f"Text to hide: {text_to_hide}")

                attachments = request.query[-1].attachments
                if attachments:
                    attachment_url = attachments[0].url
                    logger.debug(f"Attachment URL: {attachment_url}")

                    response = requests.get(attachment_url)
                    logger.debug(f"Attachment download response status code: {response.status_code}")

                    if response.status_code == 200:
                        image_stream = io.BytesIO(response.content)
                        logger.debug("Image stream created")

                        secret_image = lsb.hide(image_stream, text_to_hide)
                        logger.debug("Secret image generated")

                        output_image_stream = io.BytesIO()
                        secret_image.save(output_image_stream, format='PNG')
                        output_image_stream.seek(0)
                        logger.debug("Output image stream created")

                        await self.post_message_attachment(
                            message_id=request.message_id,
                            file_data=output_image_stream.getvalue(),
                            filename="hidden_message_image.png"
                        )
                        logger.debug("Message attachment posted")

                        yield fp.PartialResponse(text="Image with hidden message generated and attached.")
                    else:
                        logger.error(f"Failed to download attachment from URL: {attachment_url}")
                        yield fp.PartialResponse(text="Failed to download the image attachment.")
                else:
                    logger.warning("No image attachment found.")
                    yield fp.PartialResponse(text="No image attachment found.")

            elif last_message.startswith("/reveal"):
                attachments = request.query[-1].attachments
                if attachments:
                    attachment_url = attachments[0].url
                    logger.debug(f"Attachment URL: {attachment_url}")

                    response = requests.get(attachment_url)
                    logger.debug(f"Attachment download response status code: {response.status_code}")

                    if response.status_code == 200:
                        image_stream = io.BytesIO(response.content)
                        logger.debug("Image stream created")

                        try:
                            revealed_message = lsb.reveal(image_stream)
                            logger.debug(f"Revealed message: {revealed_message}")

                            yield fp.PartialResponse(text=f"Revealed message: {revealed_message}")
                        except Exception as e:
                            logger.error(f"Error revealing message from image: {str(e)}")
                            yield fp.PartialResponse(text="Failed to reveal the hidden message from the image.")
                    else:
                        logger.error(f"Failed to download attachment from URL: {attachment_url}")
                        yield fp.PartialResponse(text="Failed to download the image attachment.")
                else:
                    logger.warning("No image attachment found.")
                    yield fp.PartialResponse(text="No image attachment found.")

            else:
                logger.info("Received command other than '/hide' or '/reveal'")
                async for msg in fp.stream_request(
                    request, "GPT-3.5-Turbo", request.access_key
                ):
                    yield msg

            logger.info(f"Handling time: {time.time() - start_time} seconds")
        except Exception as e:
            logger.exception(f"An error occurred while processing the request: {str(e)}")
            yield fp.PartialResponse(text="An error occurred while processing your request. Please try again.")

    async def get_settings(self, setting: fp.SettingsRequest) -> fp.SettingsResponse:
        return fp.SettingsResponse(allow_attachments=True,
                                   server_bot_dependencies={"GPT-3.5-Turbo": 1},
                                   introduction_message=
"""*sigh* Yeah, yeah, I'm StegoBot or whatever. I'll make the text invisible and hide it in the image. Look, if you want to hide stupid messages in images, start your command with 

`/hide [message]` 

and attach a pic, got it? And if you need to reveal some dumb hidden message, do

`/reveal`

and attach the pic. I'm too lazy to actually encrypt anything, so don't use me for anything important, okay? My skills are limited, my attitude is apathetic, and my code is probably riddled with vulnerabilities. But hey, at least I'm too lazy to put in any actual effort to mess things up on purpose?

**CREATOR NOTE**
This bot uses steganography to hide text in images. That means it is embedding a .txt file in the image, not making words in an image *look* like they are hidden. 
/hide THIS IS MY HIDDEN MESSAGE
and you attach an image you want to hide it in.
/reveal
the image that I hid the message in, and I'll reveal it for you."""
                                   )
# this part is the annoying part because the stegano python package is not available via pip. so mount dependecy from local dir  instead
stegano_mount = Mount.from_local_dir(
    "/path/to/my/python3.12/site-packages/stegano",
    remote_path="/rootpathtomy/site-packages/stegano",
)

image = (
    Image.debian_slim()
    .apt_install("libgl1", "libglib2.0-0")  # Install required system libraries
    .pip_install("fastapi-poe==0.0.36", "requests", "pillow==10.3.0", "stegano")
)

stub = Stub("stego-poe")

@stub.function(image=image, mounts=[stegano_mount], secrets=[Secret.from_name("the-secrets-you-make-in-modal")])
@asgi_app()
def fastapi_app():
    POE_ACCESS_KEY = os.environ["POE_ACCESS_KEY"]
    bot = StegoBot(access_key=POE_ACCESS_KEY)
    app = fp.make_app(bot)
    return app
