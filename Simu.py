import os, sys, threading, time

root_dir = "./"
threads_count = 2

class Runner(threading.Thread):
    def __init__(self, command_name, command):
        self.command_name = command_name
        self.command = command
        self.result = None
        threading.Thread.__init__(self)

    def get_result(self):
        return self.result

    def run(self):
        with os.popen(self.command) as pipeout:
            output = pipeout.read()
        sys.stdout.write(self.command_name + " ... ")
        if output.find("Player 1 Wins!") > 0:
            self.result = 1
            sys.stdout.write("player 1 wins\n")
        elif output.find("Player 2 Wins!") > 0:
            self.result = -1
            sys.stdout.write("player 2 wins\n")
        else:
            self.result = 0
            sys.stdout.write("draw\n")
           
if __name__ == '__main__':
    bots = [fname for fname in os.listdir(root_dir + "example_bots") if fname.split(".")[-1] == "jar"]
   
    p1_count = 0
    p2_count = 0
    draw_count = 0
   
    if not os.path.exists("logs"):
        os.makedirs("logs")
    commands = []
   
    if 1:
        for bot in bots:
            for map_id in xrange(1, 40):           
                call_str = "java.exe -jar " + root_dir + "tools/PlayGame-1.2.jar " + \
                    root_dir + "maps/map" + str(map_id) + ".txt 1000 200 " + \
                    "logs/log_" + bot.split(".")[0] + "_map" + str(map_id) + ".txt " + \
                     "\"python " + root_dir + "MyBot.py\"" + \
                     " \"java -jar " + root_dir + "example_bots/" + bot + "\" 2>&1"
                commands.append(Runner(bot + " " + "map" + str(map_id), call_str))
    else:
        bot = "EnemyBot.py"
        for map_id in xrange(1, 3):           
            call_str = "java.exe -jar " + root_dir + "tools/PlayGame-1.2.jar " + \
                root_dir + "maps/map" + str(map_id) + ".txt 1000 200 " + \
                "logs/log_" + bot.split(".")[0] + "_map" + str(map_id) + ".txt " + \
                 "\"python " + root_dir + "MyBot.py\"" + \
                 " \"python " + root_dir + bot + "\" 2>&1"
            commands.append(Runner(bot + " " + "map" + str(map_id), call_str))
   
    pool = []
    for i in range(threads_count):
        command = commands.pop()
        print command.command
        command.start()
        time.sleep(0)
        pool.append(command)
   
    while len(pool) > 0:
        completed_tasks = filter(lambda t : not t.isAlive(), pool)
        for task in completed_tasks:
            if task.get_result() == 1:
                p1_count += 1
            elif task.get_result() == -1:
                p2_count += 1
            else:
                draw_count += 1
            pool.remove(task)
            if len(commands) > 0:
                command = commands.pop()
                command.start()
                time.sleep(0)
                pool.append(command)
           
    print "==================="
    print "Player 1 wins count =", p1_count
    print "Player 2 wins count =", p2_count
    print "Draws count =", draw_count
