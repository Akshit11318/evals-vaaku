"""Extension point for a later upload-and-compare action.

This release does not transcribe an uploaded file. Calling this function
raises immediately so a caller cannot mistake it for a working path.
"""


def compare_uploaded_audio(*_args, **_kwargs):
    raise NotImplementedError("Upload comparison is an extension point and is not implemented.")
