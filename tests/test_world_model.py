from world_model.world import WorldModel
from world_model.obstacle import Obstacle


world = WorldModel()

green = Obstacle(
    obstacle_id=1,
    color="GREEN",
    distance=0.82,
    angle=14,
    section=3
)

red = Obstacle(
    obstacle_id=2,
    color="RED",
    distance=1.10,
    angle=-8,
    section=5
)

world.add_obstacle(green)

world.add_obstacle(red)

world.print_state()