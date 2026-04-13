import nuke

"""
ask.py
---------
Provides user-facing dialog utilities for requesting confirmation in Nuke.

Wraps nuke.ask() to expose reusable validation prompts, and handles
specific cases such as notifying the user of layer additions or removals
before proceeding with an operation.
"""

def validation(msg: str) -> bool:
    proceed = nuke.ask(msg)
    return proceed

def accept_layers_variations(layers_to_add: dict, layers_to_delete: dict) -> bool:
    if not layers_to_add and not layers_to_delete:
        return True

    msg = ""
    if layers_to_add:
        msg = (f"Some layers have been added:\n"
               f"{', '.join([n['name'] for n in layers_to_add.values()])}\n\n")

    if layers_to_delete:
        msg = msg + (f"Some layers have been removed:\n"
                     f"{', '.join([n['name'] for n in layers_to_delete.values()])}\n\n")

    proceed = validation(msg)
    return proceed
