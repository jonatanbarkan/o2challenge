import datetime
from collections import defaultdict
from itertools import combinations
import networkx as nx


class O2Parser(object):

    @staticmethod
    def calculateDate(s_time):
        time_format = '%H:%M:%S'

        try:
            t = datetime.datetime.strptime(s_time, time_format)
        except ValueError:
            if '24' in s_time:
                s_time = s_time.replace('24', '23')
                hours = 1
            elif '25' in s_time:
                s_time = s_time.replace('25', '23')
                hours = 2
            t = datetime.datetime.strptime(s_time, time_format)
            t += datetime.timedelta(hours=hours)

        t = int(datetime.timedelta(hours=t.hour, minutes=t.minute, seconds=t.second, days=(t.day-1)).total_seconds()/60)
        return t

    @staticmethod
    def pars(filename):
        event_types = ["service_trip", "depot_pull_in", "depot_pull_out"]
        G = nx.DiGraph()
        buses = []
        bus_to_nodes = defaultdict(list)

        # Read input file
        # f = open(sys.argv[1], 'r')
        f = open(filename)
        # parse input file
        i = -2

        for line in f:
            i += 1
            if i == -1:
                continue
            ez = line.split(',')  # split each line
            if len(ez) != 9:
                print "Panic: illegal input line ", line

            entry = {}
            entry["bus"] = ez[1]  # Vehicle Id
            buses.append(entry["bus"])

            entry["event"] = event_types.index(ez[2])

            st = O2Parser.calculateDate(ez[3])
            entry["start_time"] = st  # start time of a ride in second from 0

            et = O2Parser.calculateDate(ez[4])
            entry["end_time"] = et  # end time of a ride in second from 0

            entry["duration_time"] = (et-st) # total duration of a ride

            entry["start_location"] = int(ez[5])  # start location of a ride
            entry["end_location"] = int(ez[7])  # end location of a ride

            G.add_node(i, entry)
            bus_to_nodes[entry["bus"]] += [i]

        buses = list(set(buses))
        num_buses = len(buses)
        num_original_G_nodes = G.number_of_nodes()

        # add "s" and "t" here!
        G.add_edges_from([("start", i) for i in range(num_original_G_nodes)])

        for bus in buses:
            nodes = bus_to_nodes[bus]

            # create the second level nodes
            for node in nodes:
                G.add_node(node+num_original_G_nodes, G.node[node].copy())

            # connect between nodes of the same bus on both levels
            #  TODO: needs to change to connect only the two real neighbours
            #  -----------------------------------------------------------
            for from_node, to_node in combinations(nodes, 2):
                if G.node[from_node]["end_location"] == G.node[to_node]["start_location"]\
                        and G.node[from_node]["end_time"] >= G.node[to_node]["start_time"]:
                    G.add_edge(from_node, to_node)
                    G.add_edge(from_node + num_original_G_nodes, to_node + num_original_G_nodes)

        # add connections between the 2 levels of the graph
        for bus1, bus2 in combinations(buses, 2, ):

            bus1_nodes = bus_to_nodes[bus1]
            bus2_nodes = bus_to_nodes[bus2]

            for ride1, ride2 in [(ride1, ride2) for ride1 in bus1_nodes for ride2 in bus2_nodes]:
                if G.node[ride1]["end_location"] == G.node[ride2]["start_location"] \
                        and G.node[ride1]["end_time"] <= G.node[ride2]["start_time"] <= G.node[ride1]["end_time"]:
                    G.add_edge(ride1, ride2 + num_original_G_nodes)

                elif G.node[ride2]["end_location"] == G.node[ride1]["start_location"] \
                        and G.node[ride2]["end_time"] <= G.node[ride1]["start_time"] <= G.node[ride2]["end_time"]:
                    G.add_edge(ride2, ride1 + num_original_G_nodes)

        G.add_edges_from([(i, "target") for i in range(num_original_G_nodes*2)])

        return G, num_original_G_nodes, bus_to_nodes


# G, j, bus_to_nodes = O2Parser.pars()
# print(G.edges())
# print (list(G.nodes(data=True)))
