import os
import logging

logger = logging.getLogger(__name__)

class OutputStorage:
    """Handles saving parsed structured data to disk."""
    
    def save(self, content: str, file_path: str):
        logger.info(f"Saving output to {file_path}")
        
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
            
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
        
        logger.info("Save successful.")
