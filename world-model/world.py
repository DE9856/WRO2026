from world_model.vehicle_state import VehicleState
from world_model.track import Track
from world_model.memory import MemoryManager


class WorldModel:

    def __init__(self):

        self.vehicle = VehicleState()

        self.track = Track()

        self.memory = MemoryManager()

    def add_obstacle(self, obstacle):

        self.memory.add_obstacle(obstacle)

    def print_state(self):

        print("\n" + "=" * 50)
        print("WORLD MODEL")
        print("=" * 50)

        print(self.vehicle)

        print("\nObstacles:\n")

        obstacles = self.memory.get_all_obstacles()

        if len(obstacles) == 0:

            print("No obstacles stored.")

        else:

            for obs in obstacles:

                print(obs)

        print("=" * 50 + "\n")