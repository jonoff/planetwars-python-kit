#!/usr/bin/python
from planetwars import BaseBot, Game, NOBODY, ENEMIES
from planetwars import player
from planetwars.attack import *
from logging import getLogger
from myuniverse import *
from helper_functions import *
import sys
from copy import copy

log = getLogger(__name__)

#java -jar tools/PlayGame-1.2.jar maps/map26.txt 1000 100 log.txt "python MyBot.py" "python MyBot.py" | python visualizer\visualize_localy.py
    
def turns_to_profit_filter(planet):
    return planet.turns_till_profit < TURNS_TO_PROFIT_MAX

def not_mine_filter(planet):
    return planet.in_future(None).owner != player.ME
    
def neutral_filter(planet):
    return not_mine_filter(planet) and turns_to_profit_filter(planet)

def prioritize_attack_list(universe):
    return
     
def frontline_attack(universe, frontline):
    '''This planet is on the frontline (i.e. it is the nearest friendly to at least one enemy planet)'''
    #Attack closest enemy or neutral if ships > ATTACK_RATIO
    nearest_enemy = frontline.find_nearest_neighbor(owner=player.ENEMIES)
    if not nearest_enemy:
        return
        
    distance_to_ne = frontline.distance(nearest_enemy)
    nearest_neutral = frontline.find_nearest_neighbor(owner=player.NOBODY, extra_condition=neutral_filter)
    
    #attack nearest enemy if closer to me
    future_enemy = nearest_enemy.in_future(distance_to_ne)
    nearest_enemies_nearest_friend = nearest_enemy.find_nearest_neighbor(owner=player.ENEMIES)
    enemy_planets_in_range = [p for p in universe.enemy_planets if p.distance(nearest_enemy) <= distance_to_ne]
    
    #send enough ships to cover all nearby enemy planets and their growth (plus an extra growth turn so we'll be alive at least 1 turn)
    log.info("+enemy targeting:%s@%s" % (enemy_planets_in_range, distance_to_ne))
    for x in enemy_planets_in_range:
        log.info("+enemy planet %s@%s  future: %s" % (x, x.distance(frontline), x.in_future(distance_to_ne)))
        
    ships_to_beat = sum(x.growth_rate + x.in_future(distance_to_ne).ship_count for x in enemy_planets_in_range)
    log.info("+ships_to_beat:%s" % ships_to_beat)
    
    if frontline.ship_count > ships_to_beat and future_enemy.owner != player.ME:
        log.info("+attacking far enemy with enough ships %s" % nearest_enemy)
        universe.add_attack(frontline, nearest_enemy, frontline.ship_count, ATTACK_PRIORITY)
        
    #Start near enemy on first turn, only take what I can spare, we might swap planets
    elif not nearest_enemies_nearest_friend:
        spare_ships = min(frontline.ship_count, frontline.ship_count - nearest_enemy.ship_count + frontline.growth_rate*distance_to_ne)
        if spare_ships < 1:
            return
            
        planet = copy(frontline)
        log.info("+spare_ships:%s" % spare_ships)
        planet.ship_count = spare_ships
        
        table = []
        candidates = [p for p in universe.nobodies_planets if p.distance(frontline) < p.distance(nearest_enemy)]
        #knapsack of planets closer to me
        for c in candidates:
            nearest_enemy_planet = c.find_nearest_neighbor(owner=player.ENEMIES)
            #Check if planet will be caputured before our ships will get there
            future_planet = c.in_future(planet.distance(c))
            if future_planet.owner == player.ME:
                continue
                
            #Use the future state in case other fleets are in root
            cost = future_planet.ship_count+1
            value = (100 - c.distance(planet)) * c.growth_rate
            table.append((c, cost, value))
    
        list = knapsack(table, planet.ship_count)
        for (netural_planet, ships, value) in list:
            log.info("--+attacking Neutral %s" % (netural_planet))
            universe.add_attack(planet, netural_planet, ships, ATTACK_NEUTRAL_PRIORITY)
        
    elif nearest_neutral and nearest_enemy:
        #neutrals that will gain net profit by attacking along the way to enemy AND
        #the time is takes to profit + the additional journey has to be less than the current distance
        possible_neutrals = [p for p in universe.nobodies_planets if p.in_future(None).owner == player.NOBODY and\
            frontline.ship_count > p.ship_count and p.growth_rate > 0 and \
            p.distance(frontline) <= frontline.distance(nearest_enemy) and \
            p.turns_till_profit + (frontline.distance(p) + p.distance(nearest_enemy) - frontline.distance(nearest_enemy)) <= frontline.distance(nearest_enemy)]
        #p.turns_till_profit <= (frontline.distance(p) + p.distance(nearest_enemy) - frontline.distance(nearest_enemy))
        log.info("possible neutrals:%s" % (possible_neutrals))
        
        for p in possible_neutrals:
            log.info("possible_neutral:%s@%s, total_dist:%s" % (p, frontline.distance(p), frontline.distance(p) + p.distance(nearest_enemy) - frontline.distance(nearest_enemy)))
            
        if possible_neutrals:            
            best_neutral = sorted(possible_neutrals, key=lambda p: p.turns_till_profit + p.distance(frontline))[0]
            log.info("+nearest_neutral %s ATTACKING best_netural %s" % (nearest_neutral, best_neutral))
            universe.add_attack(frontline, best_neutral, frontline.ship_count, ATTACK_NEUTRAL_PRIORITY)
            
        
        
def send_to_frontline(universe, planet):
    frontline = sorted(universe.frontlines, key=lambda a: planet.distance(a))[0]
    log.info("--move to Frontline %s" % (frontline))
    universe.add_attack(planet, frontline, planet.ship_count, FRONTLINES_PRIORITY)
        
def send_to_frontlines_or_neutral(universe, planet):
    '''Determines which planet to send ships from the back of the galaxy to.'''
    if universe.frontlines:
        frontline = sorted(universe.frontlines, key=lambda a: planet.distance(a))[0]
    nearest_neutral = planet.find_nearest_neighbor(owner=player.NOBODY, extra_condition=neutral_filter)

    if nearest_neutral and planet.distance(nearest_neutral) < planet.distance(frontline)/2:
        log.info("--NETURAL ATTACK %s" % planet)
        attack_close_neutral_planets(universe, planet)
    elif frontline:
        log.info("--move to Frontline %s" % (frontline))
        universe.add_attack(planet, frontline, planet.ship_count, FRONTLINES_PRIORITY)

def determine_frontlines(universe):
    '''Calculates which planets to launch attacks from (Frontline is defined as a friendly planet whose nearest occupied neighbor is a enemy planet)'''
    universe.frontlines = []
    future_planets = []
    
    candidates = copy(universe.my_planets)
    #include planets I'm attacking and will own
    for target in universe.my_targets:
        future_planet = target.in_future(None)        
        if future_planet.owner == player.ME and target not in future_planets:
            future_planets.append(target)
     
    future_planets = Planets(future_planets)
    candidates = candidates | future_planets
    
    #add my planets that are closest to enemy
    for planet in candidates:
        nearest_occupied_planet = sorted((candidates | Planets(universe.enemy_planets)) - planet, key=lambda a: planet.distance(a))[0]
                
        if nearest_occupied_planet.owner in player.ENEMIES and planet not in universe.frontlines:
            future_planet = planet.in_future(None)
            if future_planet.owner == player.ME:
                universe.frontlines.append(planet)
            '''else:
                next_front = planet.find_nearest_neighbor(owner=player.ME)
                if next_front:
                    universe.frontlines.append(next_front)'''
                
    #add my planets that an enemy is closest to
    for enemy_planet in universe.enemy_planets:
        nearest_friendly_planet = sorted(candidates, key=lambda a: enemy_planet.distance(a))[0]
                        
        if nearest_friendly_planet not in universe.frontlines:
            future_planet = nearest_friendly_planet.in_future(None)
            #if future_planet.owner not in player.ENEMIES:
            universe.frontlines.append(nearest_friendly_planet)
            '''else:
                next_front = nearest_friendly_planet.find_nearest_neighbor(owner=player.ME)
                if next_front:
                    universe.frontlines.append(next_front)'''
    
    #enemy has no planets,  hmm need an assert()
    if not universe.frontlines:
        if universe.enemy_planets:
            log.info("FRONTLINE EMPTY with enemy planets:%s" % universe.enemy_planets)
        universe.frontlines = [x for x in universe.my_planets]
    
    
    log.info("--frontlines %s" % universe.frontlines)

def attack_close_neutral_planets(universe, planet):
    '''Allots ships to the DP knapsack solution of neutral planets closer to planet than to enemy'''
    nearest_enemy_planet = planet.find_nearest_neighbor(owner=player.ENEMIES)
    best_neutral = None
    
    if planet.ship_count == nearest_enemy_planet.ship_count:
        ATTACK_MIDDLE_PLANETS = 0
    else:
        ATTACK_MIDDLE_PLANETS = 1
    
    distance = planet.distance(nearest_enemy_planet)/2.0 + ATTACK_MIDDLE_PLANETS
    plist = knapsack_of_capturable_planets(universe, planet, distance)
    
    possible_neutrals = [p for p in universe.nobodies_planets if p.in_future(None).owner == player.NOBODY and\
            planet.ship_count > p.ship_count and p.growth_rate > 0 and \
            p.turns_till_profit <= (planet.distance(nearest_enemy_planet) - (planet.distance(p) + p.distance(nearest_enemy_planet)))]

    for p in possible_neutrals:
        log.info("possible_neutral:%s@%s, total_dist:%s" % (p, planet.distance(p), planet.distance(p) + p.distance(nearest_enemy_planet) - planet.distance(nearest_enemy_planet)))
    if possible_neutrals:            
        best_neutral = sorted(possible_neutrals, key=lambda p: p.turns_till_profit)[0]
            
    #nearest_neutral = planet.find_nearest_neighbor(owner=player.NOBODY, extra_condition=neutral_filter)
    nearest_frontline = sorted(universe.frontlines, key=lambda a: planet.distance(a))[0]
    
    total_growth = sum(x[0].growth_rate for x in plist)
    #log.error("distance: %s, LIST: %s  total_growth for ATTACKABlE PLANETS: %s" % (distance, plist, total_growth))
    
    #not enough ships on this planet, combine from others
    if len(plist) == 0 and best_neutral:
        log.info("--not enough ships, trying best neutral%s" % best_neutral)
        allot_reinforcements_to_neutral(universe, planet, best_neutral, ATTACK_NEUTRAL_PRIORITY)
        return
    
    '''#send to frontline (or self) if enemy nearby and has better growth and netural is not on the way to frontline
    elif total_growth < nearest_enemy_planet.growth_rate:
        if best_neutral: 
            #log.info("+nearest_neutral %s ATTACKING best_netural %s" % (nearest_neutral, best_neutral))
            universe.add_attack(planet, best_neutral, planet.ship_count, ATTACK_NEUTRAL_PRIORITY)
            return
            
            
    
     and \
         (planet.distance(nearest_neutral) + nearest_neutral.distance(nearest_enemy_planet)) > planet.distance(nearest_enemy_planet) + (planet.distance(nearest_enemy_planet) / 3.0): #or \
         nearest_neutral.distance(nearest_frontline) < nearest_neutral.distance(planet):
        log.warning("--NOT ATTACKING, sending to frontline/attack. total_growth %s < nearest_enemy_planet.growth_rate %s, planet.distance(nearest_neutral):%s, nearest_neutral.distance(nearest_enemy_planet)%s, planet.distance(nearest_enemy_planet):%s" % (total_growth,  nearest_enemy_planet.growth_rate, planet.distance(nearest_neutral), nearest_neutral.distance(nearest_enemy_planet),planet.distance(nearest_enemy_planet)))
        
        if nearest_frontline == planet and planet.ship_count > nearest_enemy_planet.in_future(distance).ship_count:
            log.info("Attacking, nearest_enemy%s" % (nearest_enemy_planet))
            universe.add_attack(planet, nearest_enemy_planet, planet.ship_count, ATTACK_NEUTRAL_PRIORITY)
        else:
            universe.add_attack(planet, nearest_frontline, planet.ship_count, ATTACK_NEUTRAL_PRIORITY)
        return'''
        
        
    #send to frontline if high threat
    #elif nearest_frontline != planet and 

    #attack neutrals if nothing else takes precendence
    for (neutral_planet, ships, value) in plist:
        log.info("--+attacking Neutral %s@%s" % (neutral_planet, planet.distance(neutral_planet)))
        if len(plist) == 1:
            log.info("SeNDING ALL SHIPS")
            ships = planet.ship_count
        universe.add_attack(planet, neutral_planet, ships, ATTACK_NEUTRAL_PRIORITY)

def steal_neutral_planets(universe):
    for netural_planet in universe.neutral_targets:
        #enemy wasting ships! ignore for now
        fp = netural_planet.in_future(None)
        if fp.owner == player.NOBODY:
            log.info("ENEMY WASTE DETECTED, huzzah!, to np:%s fp:%s" % (netural_planet, fp))
            continue
        log.info("STEAL netural_planet: %s" % netural_planet)
        allot_reinforcements_to(universe, netural_planet, STEAL_NEUTRAL_PRIORITY)

def attack_enemy_from(universe, planet):
    log.info("ATTACK enemy from %s" % planet)
    for enemy_planet in universe.enemy_planets:
        #log.info("Planet TO DEFEND: %s" % planet)
        #allot_reinforcements_to(universe, planet, DEFEND_PRIORITY)
        pass

def defend_planets(universe):
    for planet in universe.my_planets_under_attack:
        log.info("DEFEND Planet: %s" % planet)
        log.info("attacks: %s" % universe.find_attacks(destination=planet))
        allot_reinforcements_to(universe, planet, DEFEND_PRIORITY)

def affective_ship_count(universe, planet):
    '''Returns the number of ships that can be sent out this turn, and aren't needed for future turns'''

    arriving_fleets = universe.find_fleets(destination=planet, owner=player.ENEMIES)
    planned_attacks = sorted(universe.find_attacks(source=planet), key=lambda f: f.turns_to_wait)

    #To find out how many ships we can spare this turn, look at all arriving enemy fleets and all departing future fleets
    #The number of ships the planet has on each of these turns limits how many can be sent now
    #The lowest number of ships on all these turns is how many "extra" ships the planet has
    available_ships = planet.ship_count

    #check for ships reserved for defense
    for fleet in arriving_fleets:
        future_planet = planet.in_future(fleet.turns_remaining)
        if future_planet.owner != player.ME:
            log.info("Currently going to lose planet: %s" % (future_planet))
            available_ships = 0
        else:
            if future_planet.ship_count < available_ships:
                available_ships = future_planet.ship_count

    #check for departing ships in the future
    for fleet in planned_attacks:
        future_planet = planet.in_future(fleet.turns_to_wait)
        #log.info("future_planet %s fleet.turns_to_wait %s" % (future_planet, fleet.turns_to_wait))
        if future_planet.ship_count < available_ships:
            available_ships = future_planet.ship_count

    #log.info("arriving_fleets %s, planned_attacks %s available_ships %s" % (arriving_fleets, planned_attacks, available_ships))

    return available_ships


def build_attack_list(universe):
    #general functions operate on all planets that fall under the category
    defend_planets(universe)
    #TODO defend frontlines underattack from afar with enemy planet nearby that will support attacks incoming
    
    steal_neutral_planets(universe)
    
    #Each planet's specific function
    for planet in universe.my_planets:
        log.info("Planning Plant: %s" % planet)
        
        nearest_frontline = sorted(universe.frontlines, key=lambda a: planet.distance(a))[0]
        nearest_fl_enemy = nearest_frontline.find_nearest_neighbor(owner=player.ENEMIES)
        
        #TODO: Ships who have neutral close but will be captured don't sent to front lines

        #Account for ships reserved for use in future turns
        real_ship_count = planet.ship_count
        planet.ship_count = affective_ship_count(universe, planet)
        if planet.ship_count < 1:
            planet.ship_count = real_ship_count
            log.info("All reserved, skipping")
            continue
        
        nearest_enemy = planet.find_nearest_neighbor(owner=player.ENEMIES)
        nearest_neutral = planet.find_nearest_neighbor(owner=player.NOBODY, extra_condition=neutral_filter)
        
        if not nearest_neutral and not nearest_enemy:
            log.warning("--NO NEUTRAL/enemy sending to front")
            send_to_frontline(universe, planet)
        
        #FIX support frontlines
        #elif nearest_frontline.in_future(None).ship_count < nearest_fl_enemy.ship_count:
            #If frontline is underattack, ignore neturals and support him
            #send_to_frontline(universe, planet)
        
        elif nearest_neutral and nearest_enemy and planet.distance(nearest_enemy) > 2 * planet.distance(nearest_neutral) and planet.distance(nearest_neutral) < nearest_frontline.distance(nearest_neutral): #MAGIC NUMBER
            #Intial planets are at considered frontline but they much closer to neutrals than to enemy, intially span out to neutral planets
            log.info("+INTIAL expand mode")
            log.info("+nearest_neutral%s@%s nearest_enemy %s@%s" % (nearest_neutral, planet.distance(nearest_neutral), nearest_enemy, planet.distance(nearest_enemy)))
            
            attack_close_neutral_planets(universe, planet)

        #if planet is a frontline, attack enemy or a neutral planet
        elif planet in universe.frontlines:
            log.info("+FRONTLINE %s" % planet)
            frontline_attack(universe, planet)
            
        else:
            log.info("+sending ships out")
            #Moves ships to the closest frontline or neutral planet
            send_to_frontlines_or_neutral(universe, planet)

        #revert to orignal ship count
        planet.ship_count = real_ship_count
    

def clean_attack_list(universe):
    '''Purges attacks from the attack list that were for a fleet that has been pre-empted by a new enemy fleet'''

    for new_fleet in universe.new_enemy_fleets:
        planet = new_fleet.destination
        turn_to_reschedule = new_fleet.turns_remaining
        #Clear out fleets scheduled to land after new fleet, they will be re-optimized
        outdated_attacks = universe.find_attacks(destination=planet)
        #outdated_attacks = [a for a in outdated_attacks if a.turns_remaining > turn_to_reschedule]
        for a in outdated_attacks:
            universe.remove_attack(a)

class jbot(BaseBot):
    """Another bot that spews out ships."""
    def do_turn(self):
        #Get new enemy atatcks
        self.universe.new_enemy_fleets = self.universe.enemy_fleets - self.universe._old_enemy_fleets

        #Build lists of my and neutral planets under attack
        self.universe.neutral_targets = [p for p in self.universe.enemy_targets if p.owner==player.NOBODY]
        self.universe.my_planets_under_attack = [p for p in self.universe.enemy_targets if p.owner==player.ME]
        
        planets_to_help = [p for p in self.universe.my_targets if p.in_future(None).owner != player.ME]
        self.universe.my_planets_under_attack.extend(planets_to_help)
        
        #Go through new enemy fleets and planet lists, planning attacks
        clean_attack_list(self.universe)
        determine_frontlines(self.universe)
        build_attack_list(self.universe)
        prioritize_attack_list(self.universe)
        self.universe.send_attacks()

Game(jbot, universe_class=MyUniverse, planet_class=MyPlanet)
