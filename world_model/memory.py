class MemoryManager:

    def __init__(self):

        self.obstacles = []

    def add_obstacle(self, obstacle):

        self.obstacles.append(obstacle)

    def get_all_obstacles(self):

        return self.obstacles

    def clear(self):

        self.obstacles.clear()