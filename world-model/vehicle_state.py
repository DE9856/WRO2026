class VehicleState:

    def __init__(self):

        self.current_lap = 1

        self.current_section = 1

        self.direction = None

        self.speed = 0

        self.steering_angle = 0

    def __str__(self):

        return (
            f"Lap={self.current_lap} | "
            f"Section={self.current_section}"
        )