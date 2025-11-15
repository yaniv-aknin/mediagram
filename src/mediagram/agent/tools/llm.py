import llm as llm_lib

from mediagram.config import AVAILABLE_MODELS, patch_docstring
from ..callbacks import ProgressMessage, SuccessMessage, ErrorMessage
from . import tool, get_tool_subdir


@patch_docstring
@tool
async def llm(model: str, infile: str, outfile: str, prompt: str):
    """Process a file through an LLM (Large Language Model).

    This tool allows processing text files through various LLMs for tasks like:
    - Summarizing long documents
    - Translating text
    - Extracting information
    - Reformatting content
    - Analyzing text

    This tool is not affected by /tlimit - it can process large outputs.

    Args:
        model: Model alias or full model name. Available aliases: {available_models}
        infile: Path to input file (relative to working directory)
        outfile: Path to output file (relative to working directory)
        prompt: The prompt/instruction for the LLM
    """
    tool_subdir = get_tool_subdir()
    if not tool_subdir:
        yield ErrorMessage(text="Error: No working directory configured")
        return

    infile_path = tool_subdir / infile
    if not infile_path.exists():
        yield ErrorMessage(text=f"Error: Input file not found: {infile}")
        return

    if not infile_path.is_file():
        yield ErrorMessage(text=f"Error: Input path is not a file: {infile}")
        return

    outfile_path = tool_subdir / outfile

    yield ProgressMessage(
        text=f"Reading input file: {infile}",
        completion_ratio=0.1,
    )

    try:
        input_text = infile_path.read_text()
    except Exception as e:
        yield ErrorMessage(text=f"Error reading input file: {e}")
        return

    resolved_model = AVAILABLE_MODELS.get(model, model)

    yield ProgressMessage(
        text=f"Processing with model: {resolved_model}",
        completion_ratio=0.3,
    )

    try:
        llm_model = llm_lib.get_model(resolved_model)
    except Exception as e:
        available = ", ".join(f'"{k}"' for k in AVAILABLE_MODELS.keys())
        yield ErrorMessage(
            text=f"Error loading model '{model}': {e}\n\nAvailable model aliases: {available}\n\nYou can also use any full model name supported by the llm library."
        )
        return

    try:
        full_prompt = f"{prompt}\n\n{input_text}"
        response = llm_model.prompt(full_prompt)
        output_text = response.text()

        yield ProgressMessage(
            text="Writing output file",
            completion_ratio=0.9,
        )

        outfile_path.write_text(output_text)

        file_size = len(output_text)
        yield SuccessMessage(
            text=f"Successfully processed {infile} -> {outfile} ({file_size:,} chars)"
        )

    except Exception as e:
        yield ErrorMessage(text=f"Error processing with LLM: {e}")
