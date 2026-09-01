# app/utils/visualizaton.py
from pathlib import Path
from loguru import logger
from app.graph.workflow import app as graph_app

def generate_graph_visualization(output_file: str = "workflow_graph.png") -> str:
    """
    Renders and saves the LangGraph workflow visualization as an image.
    Requires graphviz or drawmermaid dependencies.
    """
    output_path = Path(output_file)
    try:
        # Generate PNG byte stream directly from LangGraph
        image_bytes = graph_app.get_graph().draw_mermaid_png()
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        logger.info(f"Graph visualization saved to {output_path.resolve()}")
        return str(output_path.resolve())
    except Exception as e:
        logger.warning(f"Failed to render PNG graph automatically (missing graphviz/mermaid dependencies): {e}")
        logger.info("Printing ASCII / Mermaid text representation instead:")
        mermaid_text = graph_app.get_graph().draw_mermaid()
        print("\n--- MERMAID GRAPH REPRESENTATION ---")
        print(mermaid_text)
        print("------------------------------------\n")
        return mermaid_text

if __name__ == "__main__":
    generate_graph_visualization()