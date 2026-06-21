import logging

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LiemVRAM")

class VRAMManager:
    """
    Simulates GPU VRAM allocations for Local LLM running (e.g., 8GB VRAM limit).
    Implements Scale-to-Zero model offloading to host system memory.
    """
    def __init__(self, limit_gb: float = 8.0):
        self.limit_gb = limit_gb
        self.current_vram_gb = 0.0
        self.loaded_models = {}  # model_name -> size_gb

        # Define model sizes in GB
        self.model_sizes = {
            "axel": 1.5,
            "planner": 3.0,
            "router": 1.0,
            "scheduler": 1.0,
            "backend_agent": 4.5,
            "qa_agent": 3.0,
            "context_compressor": 1.5
        }

    def load_model(self, model_name: str, device: str = "cuda") -> bool:
        size = self.model_sizes.get(model_name, 2.0)
        
        # Check if already loaded
        if model_name in self.loaded_models:
            logger.info(f"[VRAM] Model {model_name} is already loaded on {device}.")
            return True

        logger.info(f"[VRAM] Requesting load of {model_name} ({size}GB) on {device}...")

        # If loading exceeds limits, offload other idle models
        while self.current_vram_gb + size > self.limit_gb:
            if not self.loaded_models:
                logger.error(f"[VRAM] OOM! Model {model_name} ({size}GB) exceeds total VRAM limit ({self.limit_gb}GB).")
                return False
            
            # Offload the first loaded model to free up VRAM
            victim = list(self.loaded_models.keys())[0]
            logger.warning(f"[VRAM] Limit exceeded! Automatic evicting {victim} to system RAM to free up VRAM.")
            self.unload_model(victim)

        self.loaded_models[model_name] = size
        self.current_vram_gb += size
        logger.info(f"[VRAM] Successfully loaded {model_name} on {device}. Current VRAM Usage: {self.current_vram_gb:.2f}GB / {self.limit_gb}GB")
        return True

    def unload_model(self, model_name: str) -> bool:
        if model_name not in self.loaded_models:
            logger.info(f"[VRAM] Model {model_name} is not in VRAM.")
            return False

        size = self.loaded_models.pop(model_name)
        self.current_vram_gb -= size
        logger.info(f"[VRAM] Scale-to-Zero: Unloaded {model_name} to system RAM. Current VRAM Usage: {self.current_vram_gb:.2f}GB / {self.limit_gb}GB")
        return True

    def get_vram_usage(self) -> float:
        return self.current_vram_gb
