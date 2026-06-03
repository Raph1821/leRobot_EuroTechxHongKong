class PatrolMode:
    def __init__(self, debug: bool = False) -> None:
        self._debug = debug

    def process_frame(self, frame) -> None:
        pass

    def reset(self) -> None:
        pass

    def print_debug_state(self) -> None:
        print("\n--- PATROL mode state ---")
        print(f"  debug: {self._debug}")
        print("-------------------------")

    def set_debug(self, enabled: bool) -> None:
        self._debug = enabled
