class BuildingCompiler:
    """
    Mock BuildingCompiler math engine as specified.
    This will be replaced/wired with the actual math engine later.
    """
    def __init__(self, plot_width: float, plot_depth: float):
        self.plot_width = plot_width
        self.plot_depth = plot_depth
        self.setbacks = {}

    def apply_setbacks(self, front: float, back: float = 0.0, sides: float = 0.0):
        self.setbacks = {
            "front": front,
            "back": back,
            "left": sides,
            "right": sides
        }
