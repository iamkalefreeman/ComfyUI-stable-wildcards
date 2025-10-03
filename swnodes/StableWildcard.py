# The MIT License (MIT)
#
# Copyright © 2023 Michael Wolfe (DigitalIO)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import sys
from random import Random
import re
import server
from aiohttp import web
from typing import Dict, Any, List, Tuple


@server.PromptServer.instance.routes.post("/stable-wildcards/process")
async def process_stable_wildcards(req):
    json_data = await req.json()
    prompt = StableWildcard.process_wildcards(json_data['prompt'], json_data['seed'])
    return web.json_response({"prompt": prompt}, content_type='application/json')


class StableWildcard:
    """
    ComfyUI Custom Node
    Implements wildcards using a stable seed to make workflows reproducible after creation
    """

    def __init__(self):
        pass

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Prompt String",)
    OUTPUT_NODE = False
    FUNCTION = "execute"

    # A reusable wildcard pattern matches any string with brackets {}
    # but will not select over other wildcards.
    WILDCARD_PATTERN = re.compile('{[^{}]+}')

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # Without dynamicPrompts set to false ComfyUI will randomize our prompt before we get to it!
                "prompt" : ('STRING', {'default': '', 'multiline': True, 'dynamicPrompts': False}),
                "seed"   : ('INT', {'default': 0, 'min': 0, 'max': sys.maxsize}),

                # Currently unused, but if a breaking change must be introduced
                # it can be used to provide backwards compatibility.
                "version": ([1], {'default': 1})
            },
            "hidden"  : {
                "id"      : "UNIQUE_ID",
                "png_info": "EXTRA_PNGINFO",
            },
            "optional": {}
        }

    @staticmethod
    def process_wildcards(prompt, seed):
        """
        Process wildcards using a seed to produce stable output.
        To achieve stable results a new random object is created
        using the given seed.
        """
        if prompt is None:
            raise TypeError("prompt cannot be None")
        if not isinstance(prompt, str):
            raise TypeError(f"prompt must be a string, but got {type(prompt).__name__}")
        if seed is None:
            raise TypeError("seed cannot be None")
        if not isinstance(seed, int):
            raise TypeError(f"seed must be an integer, but got {type(seed).__name__}")

        # Setup RNG
        rng = Random(int(seed))
        
        # Search & replace matches
        match = StableWildcard.WILDCARD_PATTERN.search(prompt)
        while match:
            # Get the options - Remove the {}, split by | character
            # Because the search pattern requires at least one character,
            # ops is guaranteed to have at least one option
            ops = match.group()[1:-1].split('|')

            if not ops:
                continue
            
            # Pick a random option.
            pick = ops[rng.randint(0, len(ops) - 1)]
            
            # Replace the match and update the string
            # Limit one match incase there are repeated wildcards
            prompt = prompt.replace(match.group(), pick, 1)

            # Search for more wildcards
            match = StableWildcard.WILDCARD_PATTERN.search(prompt)
        return prompt

    def execute(self, prompt, seed, **kwargs):
        """
        Process the wildcards for execution
        """
        if prompt is None:
            raise TypeError("prompt cannot be None")
        if not isinstance(prompt, str):
            raise TypeError(f"prompt must be a string, but got {type(prompt).__name__}")
        if seed is None:
            raise TypeError("seed cannot be None")
        if not isinstance(seed, int):
            raise TypeError(f"seed must be an integer, but got {type(seed).__name__}")

        # Process the wildcards
        prompt = self.process_wildcards(prompt, seed)

        # Output result console
        print(f'\033[96m Stable Wildcard: ({seed}) "{prompt}"\033[0m')

        unique_id = kwargs.get('id')
        png_info = kwargs.get('png_info')

        # Save output into metadata if everything exists
        if unique_id is not None and png_info is not None and isinstance(png_info, dict):
            # Check for workflow and extra
            workflow = png_info.get('workflow')
            if workflow is not None and isinstance(workflow, dict):
                # Create extra if missing
                if 'extra' not in workflow:
                    workflow['extra'] = {}
                
                if isinstance(workflow.get('extra'), dict):
                    extra_data = workflow['extra']
                    # Create a namespace if necessary
                    if 'stable-wildcards' not in extra_data:
                        extra_data['stable-wildcards'] = {}
                    
                    # Save the result in metadata by id
                    if isinstance(extra_data.get('stable-wildcards'), dict):
                        extra_data['stable-wildcards'][unique_id] = prompt
                    else:
                        print('\033[93m Stable Wildcard: "stable-wildcards" in extra is not a dictionary, cannot save metadata.\033[0m')
                else:
                    print('\033[93m Stable Wildcard: "extra" in workflow is not a dictionary, cannot save metadata.\033[0m')
            else:
                print('\033[96m Stable Wildcard: Workflow missing or not a dictionary, output not saved in metadata\033[0m')
        else:
            print('\033[96m Stable Wildcard: Hidden input missing or invalid, output not saved in metadata\033[0m')

        return (prompt,)

