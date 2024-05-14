
import os
import requests
from typing import AsyncIterable
import fastapi_poe as fp
from modal import Image, Stub, asgi_app, Secret
import logging
import time
from datetime import datetime
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def truncate_text(text, max_length=20):
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

class EchoBot(fp.PoeBot):
    async def get_response_with_context(
        self, request: fp.QueryRequest, context: fp.RequestContext
    ) -> AsyncIterable[fp.PartialResponse]:
        start_time = time.time()
       
        last_message = request.query[-1].content

        logger.info(f"Headers: {context.http_request.headers}")
        logger.info(f"Query Params: {context.http_request.query_params}")
        logger.info(f"Last Message: {last_message}")

        if last_message.startswith("/generate"):
            lines = last_message.split("\n")
            prompt = lines[0][10:].strip()

            negative_prompt = None
            image = None
            strength = None
            model = None
            seed = None
            output_format = None  
            aspect_ratio = None

            for line in lines[1:]:
                line = line.strip()
                if line.startswith("Negative Prompt:"):
                    negative_prompt = line.split(":", 1)[1].strip()
                elif line.startswith("Strength:"):
                    strength = float(line.split(":", 1)[1].strip())
                elif line.startswith("Model:"):
                    model = line.split(":", 1)[1].strip()
                elif line.startswith("Seed:"):
                    seed = int(line.split(":", 1)[1].strip())
                elif line.startswith("Output Format:"):
                    output_format = line.split(":", 1)[1].strip()
                elif line.startswith("Aspect Ratio:"):
                    aspect_ratio = line.split(":", 1)[1].strip()

            if request.query[-1].attachments:
                attachment = request.query[-1].attachments[0]
                attachment_url = attachment.url
                response = requests.get(attachment_url)
                if response.status_code == 200:
                    image = response.content
                else:
                    raise Exception(f"Failed to download attachment from URL: {attachment_url}")
                
                
                if strength is None:
                    strength = 0.5
            else:
                image = None

            try:
                api_key = os.environ["STABILITY_API_KEY"] 
                logger.info(f"Generating image for prompt: {prompt}")
                logger.info(f"Negative prompt: {negative_prompt}")
                image_data, filename = self.generate_image(
                    prompt, api_key, negative_prompt, image, strength, model, seed, output_format, aspect_ratio
                )

                await self.post_message_attachment(
                    message_id=request.message_id,
                    file_data=image_data,
                    filename=filename
                )

                response_text = "Image generated and attached."
                yield fp.PartialResponse(text=response_text)
            except Exception as e:
                logger.exception("An exception occurred during image generation:")
                response_text = str(e)
                yield fp.PartialResponse(text=response_text)
                
        elif last_message.startswith("/enhance"):
            input_text = last_message[9:] 
            logger.info(f"Enhancing input text: {input_text}")
            
            prompt = input_text
            query_messages = [fp.ProtocolMessage(role="user", content=prompt)]

            query_request = fp.QueryRequest(
                version="1.1",
                type="query",
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                message_id=request.message_id,
                query=query_messages
            )

            enhanced_prompt = ""
            async for msg in fp.stream_request(
                query_request, "ReversePromptGuide", request.access_key
            ):
                enhanced_prompt += msg.text

            
            start_tag = "<final prompt>"
            end_tag = "</final prompt>"
            start_idx = enhanced_prompt.find(start_tag) + len(start_tag)
            end_idx = enhanced_prompt.find(end_tag)
            final_prompt = enhanced_prompt[start_idx:end_idx].strip()

            logger.info(f"Extracted final prompt: {final_prompt}")

            
            poor_mans_prompt_messages = [fp.ProtocolMessage(role="user", content=final_prompt)]
            poor_mans_prompt_request = fp.QueryRequest(
                version="1.1",
                type="query",
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                message_id=request.message_id,
                query=poor_mans_prompt_messages
            )

            poor_mans_response = ""
            async for msg in fp.stream_request(
                poor_mans_prompt_request, "PoorMansPrompts", request.access_key
            ):
                poor_mans_response += msg.text

            logger.info(f"Response from PoorMansPrompts: {poor_mans_response}")
            yield fp.PartialResponse(text=f"Here is the response from PoorMansPrompts based on your enhanced prompt:\n\n{poor_mans_response}")
        
        elif last_message.startswith("/mojo"):
            user_message = last_message[6:].strip() 
            logger.info(f"Forwarding message to Mojo_Infinity: {user_message}")
            
            mojo_messages = [fp.ProtocolMessage(role="user", content=user_message)]
            mojo_request = fp.QueryRequest(
                version="1.1",
                type="query",
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                message_id=request.message_id,
                query=mojo_messages
            )

            async for msg in fp.stream_request(
                mojo_request, "Mojo_Infinity", request.access_key
            ):
                yield msg
        
        elif last_message.startswith("/fireworks"):
            lines = last_message.split("\n")
            prompt = lines[0][11:].strip()

            
            negative_prompt = None
            height = None
            width = None
            cfg_scale = None
            sampler = None
            samples = None
            seed = None
            steps = None
            safety_check = None
            output_image_format = None

            for line in lines[1:]:
                line = line.strip()
                if line.startswith("Negative Prompt:"):
                    negative_prompt = line.split(":", 1)[1].strip()
                elif line.startswith("Height:"):
                    height = int(line.split(":", 1)[1].strip())
                elif line.startswith("Width:"):
                    width = int(line.split(":", 1)[1].strip())
                elif line.startswith("CFG Scale:"):
                    cfg_scale = float(line.split(":", 1)[1].strip())
                elif line.startswith("Sampler:"):
                    sampler = line.split(":", 1)[1].strip()
                elif line.startswith("Samples:"):
                    samples = int(line.split(":", 1)[1].strip())
                elif line.startswith("Seed:"):
                    seed = int(line.split(":", 1)[1].strip())
                elif line.startswith("Steps:"):
                    steps = int(line.split(":", 1)[1].strip())
                elif line.startswith("Safety Check:"):
                    safety_check_value = line.split(":", 1)[1].strip().lower()
                    safety_check = safety_check_value == "true"
                elif line.startswith("Output Image Format:"):
                    output_image_format = line.split(":", 1)[1].strip()
                    if output_image_format not in ["JPEG", "PNG"]:
                        output_image_format = "JPEG"

            try:
                api_key = os.environ["FIREWORKS_API_KEY"]  
                logger.info(f"Generating image using Fireworks AI API for prompt: {prompt}")
                logger.info(f"Negative prompt: {negative_prompt}")
                image_data, filename = await self.generate_fireworks_image(
                    prompt, api_key, negative_prompt, height, width, cfg_scale, sampler, samples, seed, steps, safety_check, output_image_format
                )

                await self.post_message_attachment(
                    message_id=request.message_id,
                    file_data=image_data,
                    filename=filename
                )

                response_text = "Image generated using Fireworks AI API and attached."
                yield fp.PartialResponse(text=response_text)
            except Exception as e:
                logger.exception("An exception occurred during Fireworks AI image generation:")
                response_text = f"Error: {str(e)}"
                yield fp.PartialResponse(text=response_text)
        
        else:
            logger.info("Forwarding request to GPT-3.5-Turbo")
            async for msg in fp.stream_request(
                request, "GPT-3.5-Turbo", request.access_key
            ):
                yield msg
        
        
        resend_text = truncate_text(last_message)
        
        yield fp.PartialResponse(
        text=last_message,
        is_suggested_reply=True,
        data={"display_text": resend_text}
        )

        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"Request processed in {execution_time:.2f} seconds")
        
    def generate_image(self, prompt, api_key, negative_prompt=None, image=None, strength=None, model=None, seed=None, output_format=None, aspect_ratio=None):

        data = {
            "prompt": prompt,
            "model": model,
            "seed": seed,
        }

        if output_format:
            data["output_format"] = output_format

        if negative_prompt:
            data["negative_prompt"] = negative_prompt

        if aspect_ratio:
            data["aspect_ratio"] = aspect_ratio

        files = {"none": ''}

        if image:
            data["mode"] = "image-to-image"
            data["strength"] = strength
            files["image"] = ("image.png", image, "image/png")
        else:
            data["mode"] = "text-to-image"

        logger.info(f"Request data: {data}")

        
        if model == "sd":
            endpoint = "https://api.stability.ai/v2beta/stable-image/generate/core"
        else:
            endpoint = "https://api.stability.ai/v2beta/stable-image/generate/sd3"

        response = requests.post(
            endpoint,
            headers={
                "authorization": f"Bearer {api_key}",
                "accept": "image/*"
            },
            files=files,
            data=data,
        )

        if response.status_code == 200:
            output_format = output_format or "jpeg"  
            current_date = datetime.now().strftime('%Y/%m/%d') 
            timestamp = int(time.time())
            filename = f"{current_date}/generated_image_{timestamp}.{output_format}"
            logger.info(f"Successful response from Stability AI API")
            logger.info(f"Generated image filename: {filename}")

            return response.content, filename
        else:
            logger.error(f"Error response from Stability AI API: {response.text}")
            raise Exception(response.text)
        
    async def generate_fireworks_image(self, prompt, api_key, negative_prompt=None, height=None, width=None, cfg_scale=None, sampler=None, samples=None, seed=None, steps=None, safety_check=None, output_image_format=None):

        try:
            import fireworks.client
            from fireworks.client.image import ImageInference, Answer

            
            fireworks.client.api_key = api_key
            inference_client = ImageInference(model="stable-diffusion-xl-1024-v1-0")

            if output_image_format is None:
                output_image_format = "JPEG"  
            
            
            answer: Answer = await inference_client.text_to_image_async(
                prompt=prompt,
                negative_prompt=negative_prompt,
                cfg_scale=cfg_scale if cfg_scale is not None else 7.0,
                height=height if height is not None else 1024,  
                width=width if width is not None else 1024,  
                sampler=sampler,
                steps=steps if steps is not None else 50,  
                seed=seed if seed is not None else 0,  
                safety_check=safety_check if safety_check is not None else True,  
                output_image_format=output_image_format
            )

            if answer.image is None:
                raise RuntimeError(f"No return image, {answer.finish_reason}")
            else:
                current_date = datetime.now().strftime('%Y/%m/%d')  
                timestamp = int(time.time())
                filename = f"{current_date}/fireworks_generated_image_{timestamp}.{output_image_format.lower()}"

                logger.info(f"Successful response from Fireworks AI API")
                logger.info(f"Generated image filename: {filename}")

                return answer.image, filename

        except Exception as e:
            logger.error(f"Error generating image with Fireworks AI API: {e}")
            raise
        
    async def get_settings(self, setting: fp.SettingsRequest) -> fp.SettingsResponse:
        return fp.SettingsResponse(
            server_bot_dependencies={"GPT-3.5-Turbo": 1, "ReversePromptGuide": 1, "PoorMansPrompts": 1, "Mojo_Infinity": 1},
            allow_attachments=True,
            introduction_message="""# EchoBot Documentation

Removing this part for brevity.
"""
                            
        )

REQUIREMENTS = ["fastapi-poe==0.0.36", "requests", "fireworks-ai"]
image = Image.debian_slim().pip_install(*REQUIREMENTS)
stub = Stub("echobot-poe")

@stub.function(image=image, secrets=[Secret.from_name("echobot-secrets")])
@asgi_app()
def fastapi_app():
    POE_ACCESS_KEY = os.environ["POE_ACCESS_KEY"]
    bot = EchoBot(access_key=POE_ACCESS_KEY)
    app = fp.make_app(bot)
    return app
