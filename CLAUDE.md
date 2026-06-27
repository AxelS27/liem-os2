# LIEM OS Development Guidelines

## Reference Commands
- Run the simulated multi-agent pipeline: `python src/liem_os/main.py`
- Run the FastAPI server: `python -m src.liem_os.server`

## AI Guidelines
Whenever the user asks to simulate tasks, build features, or test multi-agent workflows:
1. **Use the Main Runner**: Execute the Liem OS pipeline script using the command `python src/liem_os/main.py` in the terminal to allow the kernel, scheduler, and event loop of Liem OS to dynamically process the agent workflow.
2. **Do Not Bypass Code**: Do not write static mock output directly to files if the goal is to simulate agent behavior. Let the Liem OS system process it.
