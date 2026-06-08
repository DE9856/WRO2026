class Obstacle:

    def __init__(
        self,
        obstacle_id,
        color,
        distance,
        angle,
        section=None
    ):

        self.id = obstacle_id

        self.color = color

        self.distance = distance

        self.angle = angle

        self.section = section

        self.confidence = 1.0

        self.first_seen = 0

        self.last_seen = 0

    def __str__(self):

        return (
            f"ID={self.id} | "
            f"COLOR={self.color} | "
            f"DIST={self.distance:.2f}m | "
            f"ANGLE={self.angle:.2f}° | "
            f"SECTION={self.section}"
        )