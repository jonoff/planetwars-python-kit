from planetwars import BaseBot, Game, NOBODY, ENEMIES
from planetwars import player
from planetwars.attack import *
from logging import getLogger
from myuniverse import *
from knapsack import knapsack

def candidate_planets(universe, target, distance):
    '''Iterates though planets to find ones with a max distance of `distance`. Returns a dictionary of lists, distance:[candidates]'''

    r = {}
    planets_in_range = sorted(universe.my_planets - target, key=lambda p: p.ship_count, reverse=True) #target is in this gropu
    #limit range to arbitrary range IN_RANGE
    planets_in_range = [x for x in planets_in_range if x.distance(target) < distance + IN_RANGE]

    #sort planets based on how close they are to distance
    for p in planets_in_range:
        ranking = p.distance(target) - distance
        r[ranking] = r.get(ranking, [])
        r[ranking].append(p)

    return r
       
def plan_attack_for_fleet(universe, planet, enemy_fleet, priority, wait_extra_turn=0):
    list_of_attacks = []

    #Update planet state to arrival of enemy_fleet
    future_turn = enemy_fleet.turns_remaining + wait_extra_turn
    future_planet = planet.in_future(future_turn)
    reinforcements_needed = future_planet.ship_count + 1

    arriving_planned_attacks = universe.find_attacks(destination=planet)
    late_arrivals = sum([x.ship_count for x in arriving_planned_attacks if (x.turns_remaining > future_turn)])

    log.info("-+Planning for enemy_fleet: %s" % enemy_fleet)
    log.info("--+future planet(%s)@%s, late_arrivals:%s, reinforcements_needed:%d" % (future_planet, future_turn, late_arrivals, reinforcements_needed))

    #if planet is a new frontline, send all ships
    #TODO
    
    if future_planet.owner == player.ME:
        #Reserve enough ships to defeat enemy fleet
        log.info("-+Reserving %s ships" % (enemy_fleet.ship_count))
        reserved_attacks = universe.find_attacks(source=planet,destination=planet)
        already_reserved = [x for x in reserved_attacks if x.turns_to_wait == future_turn and x.ship_count == enemy_fleet.ship_count]
        if not already_reserved:
            list_of_attacks.append((planet, planet, enemy_fleet.ship_count, priority, future_turn))
        return list_of_attacks
    elif future_planet.owner == player.NOBODY:
        future_planet_growth_rate = 0
    else:
        future_planet_growth_rate = future_planet.growth_rate

    all_candidates = candidate_planets(universe, planet, future_turn)
    all_candidates = sorted(all_candidates.items(), key=lambda k: k[0])
    log.info("--all_candidates: %s, " % (all_candidates))
    
    #sum all the ships in all the planets for each rank
    #total_ships = sum([sum([p.ship_count for p in list[1]]) for list in all_candidates])

    for distance_away, candidate_list in all_candidates:
        #loop through planets close enough to send fleets
        #TODO balance # ships sent
        for candidate in candidate_list:
            log.info("---Canidate %s " % candidate)
            turns_to_wait = 0
            candidate_growth_by_turn_to_send = 0

            #Calculate amount of growth between the time our ships get there and the enemy does
            grow_turns = candidate.distance(planet) - enemy_fleet.turns_remaining
            planet_growth = future_planet_growth_rate * max(grow_turns, 0)
            reinforcement_to_send = (reinforcements_needed + planet_growth)

            
            #case where we land same time as enemy on neutral, we must outnumber enemy
            if planet.owner == player.NOBODY and future_planet.owner == player.NOBODY and candidate.distance(planet) == enemy_fleet.turns_remaining and grow_turns == 0:
                log.info("----Landing same time! adjust fleets")
                reinforcement_to_send = reinforcements_needed = enemy_fleet.ship_count + 1

                
            #no other ships needed, Stop looking
            if reinforcement_to_send < 1 or reinforcements_needed < 1:
                log.info("----NO SHIPS NEEDED: reinforcements_needed %d, reinforcement_to_send %d" % (reinforcements_needed, reinforcement_to_send))
                return list_of_attacks
                
            #if the candidate is out of range, recalculate using the last fleet's arrival turn
            if candidate.distance(planet) - enemy_fleet.turns_remaining >= 0:
                #future_turn = get_future_turn(universe, planet)
                #update to my last fleet arrival
                
                #TODO FIX THISz
                #future_planet = planet.in_future(None)
                #log.info("----new future_planet%s@" % (future_planet))
                if future_planet.owner == player.ME:
                    #skip to next fleet
                    log.info("USEFUL STATEMENT HERE")
                    return list_of_attacks
                #reinforcements_needed = future_planet.ship_count + 1
                pass
                
            #send as many ships as possible
            ships_to_send = min(reinforcement_to_send, candidate.in_future(0).ship_count)
            log.info("----+candidate.distance(planet)%s enemy_fleet.turns_remaining %s and  grow_turns%s, planet_growth:%s" % ( candidate.distance(planet), enemy_fleet.turns_remaining, grow_turns, planet_growth ) )
                        
            #send additional ships in a future turn
            if(grow_turns < 0):
                #if the planet is too close, it'll wait some turns before sending ships
                turns_to_wait = abs(grow_turns) + wait_extra_turn
                log.info("----+abs(grow_turns) %s wait_extra_turn %s" % (abs(grow_turns), wait_extra_turn))

                #and the number of ships available needs to be updated.
                future_candidate = candidate.in_future(turns_to_wait)

                #skip to next planet if this one has booked all of its future ships
                if future_candidate.ship_count < 1 or future_candidate.owner != player.ME:                    
                    #continue to next canidate
                    log.info("---all future ships booked")
                    if candidate == all_candidates[-1][-1][-1]:
                        log.info("---LAST CANIDATE ABADONING")
                        return None
                    continue
                #send some of these future generated ships if needed
                log.info("----+reinforcement_to_send%s ships_to_send:%s future_candidate%s" % (reinforcement_to_send, ships_to_send, future_candidate))
                ships_to_send = min(reinforcement_to_send, future_candidate.ship_count)
            elif candidate.in_future(0).ship_count < 1:
                log.info("no ships available")
                continue
                
            #if additional fleets needed, recalc growth based on farthest away candidate
            additional_ships = (candidate.distance(all_candidates[-1][-1][-1]) * future_planet_growth_rate)

            log.info("----+reinforcements_needed %d, reinforcement_to_send %d, sending: %d" % (reinforcements_needed, reinforcement_to_send, ships_to_send))
            
            log.info("---ADDING (%d from %s->%s, in: %d turns)" % (ships_to_send, candidate, planet, turns_to_wait + candidate.distance(planet)))
            
            #last candidate can't send enough ships, abort
            if candidate == all_candidates[-1][-1][-1] and ships_to_send < reinforcement_to_send:
                log.info("---LAST CANIDATE ABADONING: %s / %s" % (ships_to_send, reinforcement_to_send))
                return None
                    
            list_of_attacks.append((candidate, planet, ships_to_send, priority, turns_to_wait))
            reinforcements_needed = reinforcement_to_send - ships_to_send

    return list_of_attacks

def attack_planet(universe, planet, priority):
    pass
    
def allot_reinforcements_to(universe, planet, priority):
    '''Determines attacks from multiple planets to a single targeted planet'''

    enemy_fleets = sorted(planet.enemy_fleets, key=lambda f: f.turns_remaining)
    log.info("enemy_fleets: %s " % (enemy_fleets))
    for enemy_fleet in enemy_fleets:
        wait_extra_turn = 0
        #special case for neutral planets, for the first incoming enemy fleet it could be beneficial to attack one turn after the enemy instead of with them
        if enemy_fleet == enemy_fleets[0] and enemy_fleet.destination.owner == player.NOBODY:
            #let enemy deal with natives if the growth rate is small enough, by waiting an extra turn
            if planet.growth_rate < planet.ship_count or enemy_fleet.ship_count < planet.ship_count:
                wait_extra_turn = 1

        #if planet is extra "good", look farther away
        #TODO if planet_worth(planet,       

        attacks = plan_attack_for_fleet(universe, planet, enemy_fleet, priority, wait_extra_turn=wait_extra_turn)
        if attacks:
            for (candidate, planet, ships_to_send, priority, turns_to_wait) in attacks:
                universe.add_attack(candidate, planet, ships_to_send, priority, turns_to_wait)
                

def allot_reinforcements_to_neutral(universe, planet, neutral, priority):    
    candidates = [p for p in universe.my_planets if p.distance(neutral) <= (planet.distance(neutral)+2) and p not in universe.frontlines]
    
    candidates = sorted(candidates, key=lambda f: f.distance(neutral))
    if neutral.in_future(None).owner != player.NOBODY:
        return
        
    ships_needed = neutral.in_future(None).ship_count + 1
    total_ships = sum(x.in_future(0).ship_count for x in candidates)
    log.info("-Combining attacks on neutral:%s with cans:%s need %s" % (neutral,candidates, ships_needed))
    
    #for c in candidates:
    #    log.info("c%s dist: %s <= %s" % (c, c.distance(neutral), (planet.distance(neutral)+2)))
    
    if total_ships > ships_needed:        
        for candidate in candidates:
            if ships_needed <= 0:
                break
            num = min(ships_needed, candidate.ship_count)
            log.info("sending %s from %s" % (num, candidate))
            universe.add_attack(candidate, neutral, num, priority)
            ships_needed -= num
    else:
        log.info("-Not enough ships to attack neutral:%s ships:%s" % (neutral, total_ships))

def knapsack_of_capturable_planets(universe, planet, distance):
    '''Returns the set of planets which can currently be captured which have the the most growth in `distance` turns'''

    candidates = [p for p in universe.not_my_planets if (planet.distance(p) < distance) and (p.turns_till_profit < TURNS_TO_PROFIT_MAX)]
    #log.error("distance: %s, LIST: %s " % (distance, candidates))

    table = []

    for c in candidates:
        nearest_enemy_planet = c.find_nearest_neighbor(owner=player.ENEMIES)
        #log.info("distance to enemy: %s " % (nearest_enemy_planet.distance(c)))
        #log.info("planet.turns_till_profit: %s " % (c.turns_till_profit))
        #Check if planet will be caputured before our ships will get there
        future_planet = c.in_future(planet.distance(c))
        #log.info("future_planet CANIDATE: %s " % (future_planet))
        if future_planet.owner == player.ME:
            continue
            
        #Use the future state in case other fleets are in root
        cost = future_planet.ship_count+1
        value = (distance - c.distance(planet)) * c.growth_rate
        table.append((c, cost, value))
    
    return knapsack(table, planet.ship_count)
