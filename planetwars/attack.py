from planetwars.util import TypedSetBase
from planetwars.player import PLAYER_MAP
from planetwars.fleet import Fleet

DEFEND_PRIORITY = 10
STEAL_NEUTRAL_PRIORITY = 8
ATTACK_NEUTRAL_PRIORITY = 6
FRONTLINES_PRIORITY = 5
ATTACK_PRIORITY = 4
LOW_PRIORITY = 1
        
class Attack(Fleet):
    def __init__(self, universe, id, owner, source, destination, ship_count, priority = LOW_PRIORITY, turns_to_wait=0):
        self.universe = universe
        self.id = id
        self.owner = PLAYER_MAP.get(int(owner))
        self.source = source
        self.destination = destination
        self.ship_count = int(ship_count)
        self.turns_to_wait = int(turns_to_wait)
        self.priority = priority
        self.trip_length = source.distance(destination)
        self.turns_remaining = int(self.trip_length) + int(self.turns_to_wait)
        
    def __repr__(self):
        return "<F(%d) #%d %s -> %s in %d turns to arrive in %d>" % (self.id, self.ship_count, self.source, self.destination, self.turns_to_wait, self.turns_remaining)
        
class Attacks(TypedSetBase):
    """Represents a set of Fleet objects.
    All normal set methods are available. Additionaly you can | (or) Fleet objects directly into it.
    Some other convenience methods are available (see below).
    """
    accepts = (Attack, )

    @property
    def ship_count(self):
        """Returns the ship count of all Fleet objects in this set"""
        return sum(f.ship_count for f in self)

    def arrivals(self, reverse=False):
        """Returns an iterator that yields tuples of (turns_to_wait, Attacks)
        for all Subfleets that arrive in this many turns in ascending order
        (use reverse=True for descending).
        """

        turn_getter = attrgetter("turns_to_wait")
        for k, attacks in groupby(sorted(self, key=turn_getter, reverse=reverse), turn_getter):
            yield (k, Attacks(attacks))
            

class EmptyAttack(Attack):
    def __init__(self):
        self.turns_remaining = 0