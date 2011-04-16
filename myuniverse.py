from planetwars.universe import Universe
from planetwars.fleet import Fleet, Fleets
from planetwars.planet import Planet, Planets
from planetwars.attack import Attack, Attacks
from planetwars.player import PLAYER_MAP
from planetwars import player
from planetwars.player import Players
from copy import copy
from planetwars.util import ParsingException, _make_id, SetDict
from logging import getLogger
import math

log = getLogger(__name__)

#Arbitrary magic numbers
IN_RANGE = 2
ATTACK_RATIO = 1.5
TURNS_TO_PROFIT_MAX = 35
ENEMY_NEAR = 25


class MyPlanet(Planet):
    def in_future(self, turns):
        """Calculates state of planet in `turns' turns."""
        planet = copy(self)
        planet.wait_extra_turn = 0
        
        arriving_fleets = self.universe.find_fleets(destination=self)
        arriving_planned_attacks = self.universe.find_attacks(source=self.universe.planets - self, destination=self)
        departing_planned_attacks = self.universe.find_attacks(source=self, destination=self.universe.planets - self)
        
        if turns is None:
            turns = reduce(lambda a, b: max(a, b.turns_remaining), arriving_fleets, 0)
            turns = reduce(lambda a, b: max(a, b.turns_remaining), arriving_planned_attacks, turns)
            turns = reduce(lambda a, b: max(a, b.turns_to_wait), departing_planned_attacks, turns)            
            #log.info(" turns:%s" % (turns))
        
        #planned fleets with same dest and source are not actually counted or sent
        #they are just reserving ships to prevent from them leaving the attacked planet
        reserved_planned_attacks = self.universe.find_attacks(source=self)
        reserved_ships_to_send = sum([x.ship_count for x in reserved_planned_attacks if (x.turns_to_wait > turns)])
                
        #Account from [0 until turns], planned departures for the current turn will leave at 0
        for i in range(0, turns+1):
            # account planet growth, not including this turns
            if planet.owner != player.NOBODY and i > 0:
                planet.ship_count = planet.ship_count + self.growth_rate

            # get fleets which will arrive in that turn
            fleets = [ x for x in arriving_fleets if x.turns_remaining == i ]
            future_fleets = [ x for x in arriving_planned_attacks if x.turns_remaining == i]
            departing_future_fleets = [ x for x in departing_planned_attacks if x.turns_to_wait == i]
            
            # assuming 2-player scenario!
            ships = []
            for id in [1,2]:
                count = sum( [ x.ship_count for x in fleets if x.owner == PLAYER_MAP.get(int(id)) ] )
                count += sum([x.ship_count for x in future_fleets if x.owner == PLAYER_MAP.get(int(id)) ])
                count -= sum([x.ship_count for x in departing_future_fleets if x.owner == PLAYER_MAP.get(int(id)) ])
                
                if PLAYER_MAP[id] == planet.owner:
                    count += planet.ship_count

                #count will equal 0 if sending all ships
                if count > 0 or (id == 1 and departing_future_fleets):
                    ships.append({'player':PLAYER_MAP.get(id), 'ships':count})
            
            # neutral planet has own fleet
            if planet.owner == player.NOBODY:
                ships.append({'player':player.NOBODY,'ships':planet.ship_count})

            # calculate outcome
            if len(ships) > 1:
                s = sorted(ships, key=lambda s : s['ships'], reverse=True)

                winner = s[0]
                second = s[1]

                if winner['ships'] == second['ships']:
                    planet.owner=planet.owner
                    planet.ship_count=0
                else:
                    planet.owner=winner['player']
                    planet.ship_count=winner['ships'] - second['ships']
            elif len(ships) == 1:
                planet.ship_count=ships[0]['ships']
                    
            if planet.id == -4:
                log.info("fleets:%s" % (fleets))
                log.info("future_fleets:%s" % (future_fleets))
                log.info("departing_future_fleets:%s" % (departing_future_fleets))
                log.info("reserved_planned_attacks:%s " % (reserved_planned_attacks))
                log.info("ships:%s reserved_ships_to_send%s" % (ships, reserved_ships_to_send))
                log.info("i%s planet:%s planet.owner%s \n" % (i, planet, planet.owner))
               
        if planet.owner == player.ME:
            planet.ship_count -= reserved_ships_to_send 
        
        return planet


    @property
    def turns_till_profit(self):
        #future_planet = self.in_future(turn)
        #if planet.owner == players.NOBODY : TODO
        return math.ceil(float(self.ship_count) / max(self.growth_rate, .01))
    
    @property
    def my_fleets(self):
        """My fleets en-route to this planet."""
        return self.universe.find_fleets(destination=self, owner=player.ME)
        
    @property
    def future_arriving_fleets(self):
        """My fleets en-route to this planet."""
        return self.universe.find_attacks(destination=self, owner=player.ME)
        
    @property
    def future_departing_fleets(self):
        """My fleets en-route to this planet."""
        return self.universe.find_attacks(source=self, owner=player.ME)
        
    @property
    def enemy_fleets(self):
        """Enemy fleets en-route to this planet."""
        return self.universe.find_fleets(destination=self, owner=player.ENEMIES)

class MyUniverse(Universe):
    def __init__(self, game, planet_class=Planet, fleet_class=Fleet, attack_class=Attack):
        self.game = game
        self.planet_class = planet_class
        self.fleet_class = fleet_class
        self.attack_class = attack_class
        self._planets = {}
        self._fleets = {}
        self._old_enemy_fleets = Fleets([])
        self._attacks = {}
        self.planet_id_map = {}
        self.planet_id = 0
        self.attack_id = 1
        self._cache = {
            "f": {
                "o": SetDict(Fleets),
                "s": SetDict(Fleets),
                "d": SetDict(Fleets),
            },
            "p": {
                "o": SetDict(Planets),
                "g": SetDict(Planets),
            },
            "a": {
                "o": SetDict(Fleets),
                "s": SetDict(Attacks),
                "d": SetDict(Attacks),
            }
        }

    def send_attacks(self):
        attacks = sorted(self._attacks.values(), key=lambda a: a.priority, reverse=True)
        log.info("attack list:" + ''.join(['\n'+str(x) for x in attacks]))
        for attack in attacks:
            if attack.turns_to_wait == 0:
                if attack.source == attack.destination:
                    #these ships were reserved so as not to leave the planet, ignore
                    log.info("RESERVED SHIPS: %s" % (attack.source))
                elif attack.source.ship_count >= attack.ship_count and attack.ship_count > 0 and attack.source.owner == player.ME:
                    attack.source.send_fleet(attack.destination, attack.ship_count)
                else:
                    #not enough ships
                    log.warning("ATTACK NOT SENT: %s from %s" % (attack, attack.source))


    def add_attack(self, *args):
        id = self.attack_id
        self.attack_id += 1
        new_attack = self.attack_class(self, id, player.ME.id, *args)
        self._attacks[id] = new_attack
        self._cache['a']['o'][new_attack.owner].add(new_attack)
        self._cache['a']['s'][new_attack.source].add(new_attack)
        self._cache['a']['d'][new_attack.destination].add(new_attack)
        return new_attack
        
    def remove_attack(self, attack):
        id = attack.id
        del self._attacks[id]
        self._cache['a']['o'][attack.owner].remove(attack)
        self._cache['a']['s'][attack.source].remove(attack)
        self._cache['a']['d'][attack.destination].remove(attack)
        log.info("REMOVING attack: %s" % (attack))

    def find_attacks(self, owner=None, source=None, destination=None):
        """
        Returns a set of attacks that matches *all* (i.e. boolean and) criteria.
        All parameters accept single or set arguments (e.g. player.ME vs. player.ENEMIES).

        Returns <Attacks> (@see attack.py) objects (a set subclass).
        """
        ret = []
        if owner:
            ret.append(self._cache['a']['o'][Players(owner)])
        if source:
            ret.append(self._cache['a']['s'][Planets(source)])
        if destination:
            ret.append(self._cache['a']['d'][Planets(destination)])
        if ret:
            if len(ret) > 1:
                return reduce(lambda x, y: x & y, ret[1:], ret[0])
            return Attacks(ret[0])
        return Attacks()

    def turn_done(self):
        toPrint = False
        _fleets = {}
        for id, fleet in self._fleets.items():
            fleet.turns_remaining -= 1
            new_id = _make_id(fleet.owner.id, fleet.ship_count, fleet.source.id, fleet.destination.id, fleet.trip_length, fleet.turns_remaining)
            if fleet.turns_remaining == 0:
                self._cache['f']['o'][fleet.owner].remove(fleet)
                self._cache['f']['s'][fleet.source].remove(fleet)
                self._cache['f']['d'][fleet.destination].remove(fleet)
            else:                
                _fleets[new_id] = fleet
        self._fleets = _fleets
        self._old_enemy_fleets = Fleets(self.enemy_fleets)
        
        
        _attacks = {}
        for id, attack in self._attacks.items():
            attack.turns_to_wait -= 1
            attack.turns_remaining = int(attack.trip_length) + int(attack.turns_to_wait)
            if attack.turns_to_wait < 0:
                self._cache['a']['o'][attack.owner].remove(attack)
                self._cache['a']['s'][attack.source].remove(attack)
                self._cache['a']['d'][attack.destination].remove(attack)
            else:
                _attacks[id] = attack
        self._attacks = _attacks
        
    @property
    def enemy_targets(self):
        """Returns all planets targeted by another player"""
        r = []
        for f in self.enemy_fleets:
            p = f.destination
            if p not in r:
                r.append(p)
        return r
        
    @property
    def my_targets(self):
        """Returns all planets targeted by me"""
        r = []
        for f in self.my_fleets:
            p = f.destination
            if p not in r:
                r.append(p)
        return r
    

