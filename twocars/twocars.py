import cplex
import sys
from parse2cars import O2Parser
import csv
from collections import defaultdict
import networkx as nx
from numba import jit


def run(max_num_of_iter, max_seconds_of_final, input_file_name, output_file_name, original_obj_coefficients=1, stable=False):
    G, J, bus_to_nodes = O2Parser.pars(input_file_name)
    # Create a cplex object for the model of the master problem
    c_master = cplex.Cplex()

    # Suppress chater of the solver (can be set to 0,1, or 2)
    c_master.parameters.simplex.display.set(0)

    # Let the solver check model before solving - to be on the safe side
    # can be set to 0 once we have a stable version
    if stable:
        c_master.parameters.read.datacheck.set(0)
    else:
        c_master.parameters.read.datacheck.set(1)

    # initial possible solution: J rides
    c_master.variables.add(obj=[original_obj_coefficients] * J)

    # create Id column of size JxJ - initial possible solution
    A = []
    for j in xrange(J):
        A.append([[j], [1]])  # add a row

    # lower bounds are set to their default value of 0.0
    # add a "=" constraint for all journeys, all journeys should be fulfilled once
    c_master.linear_constraints.add(lin_expr=A, senses="E" * J, rhs=[1] * J)

    # Solve the master problem with initial set of columns
    c_master.solve()
    # c_master.write("myfirst.lp")  # uncomment to debug the model

    if c_master.solution.get_status() != 1:  # code for optimal solution found
        print("Panic: cannot find feasible solution for the initial master problem")
        sys.exit(-1)

    print("Optimal solution value of initial master problem ", c_master.solution.get_objective_value())

    y = c_master.solution.get_dual_values()  # get dual solution from the solver

    # -------------------------------------------------------------------------------------------------------------------
    # prepare sub problem  - we do it once here and only change the objective function coefficients at each iteration.
    # the sub problem is to find a driver route that if added will help the most. we represent the problem as a graph
    # whose nodes are the possible drives and the edges are the transfers between drives...

    def addWeights(y_):
        edges = G.edges()
        for i_, j_ in edges:
            if j_ != "target":
                k = j_ if j_ < J else j_ - J
                G[i_][j_]["weight"] = y_[k]

    @jit
    def getConnectionInfo(i_, j_):
        if j_ == "target":
            return {"S_end_time": G.node[i_]["end_time"],
                    "S_time_of_beginning_of_break": G.node[i_]["end_time"],
                    "S_price": 0}

        if G.node[j_]["S_end_time"] - G.node[i_]["start_time"] <= 9 * 60:

            # there is a break of 30 min
            if G.node[j_]["start_time"] - G.node[i_]["end_time"] >= 30:
                return {"S_end_time": G.node[j_]["S_end_time"],
                        "S_time_of_beginning_of_break": G.node[i_]["end_time"],
                        "S_price": G.node[j_]["S_price"] + G[i_][j_]["weight"]}

            # check we have time to take the current ride
            if G.node[j_]["S_time_of_beginning_of_break"] - G.node[i_]["start_time"] < 4 * 60:
                return {"S_end_time": G.node[j_]["S_end_time"],
                        "S_time_of_beginning_of_break": G.node[j_]["S_time_of_beginning_of_break"],
                        "S_price": G.node[j_]["S_price"] + G[i_][j_]["weight"]}
        return {}

    @jit
    def updateShiftsInGraph(nodes):
        for i_ in nodes:
            neighbors = G[i_]
            info = defaultdict(list)
            for neighbor in neighbors:
                info[neighbor] = getConnectionInfo(i_, neighbor)

            max_neighbor = -1
            max_price = -sys.float_info.max

            for neighbor in info:
                if len(info[neighbor]) > 0 and info[neighbor]["S_price"] > max_price:
                    max_neighbor = neighbor
                    max_price = info[neighbor]["S_price"]

            G.node[i_]["S_end_time"] = info[max_neighbor]["S_end_time"]
            G.node[i_]["S_time_of_beginning_of_break"] = info[max_neighbor]["S_time_of_beginning_of_break"]
            G.node[i_]["S_price"] = info[max_neighbor]["S_price"]
            G.node[i_]["S_neighbor"] = max_neighbor

    def getShifts(y_):
        nx.set_node_attributes(G, "S_end_time", None)
        nx.set_node_attributes(G, "S_time_of_beginning_of_break", None)
        nx.set_node_attributes(G, "S_price", None)
        nx.set_node_attributes(G, "S_neighbor", None)
        addWeights(y_)

        # update second level of nodes
        for bus in bus_to_nodes:
            # the last ride of each bus is the end of all shifts
            last_ride = bus_to_nodes[bus][-1]
            G.node[last_ride + J]["S_end_time"] = G.node[last_ride]["end_time"]
            G.node[last_ride + J]["S_time_of_beginning_of_break"] = G.node[last_ride]["end_time"]
            G.node[last_ride + J]["S_price"] = 0
            G.node[last_ride + J]["S_neighbor"] = "target"

            # find shifts from all other rides
            nodes = bus_to_nodes[bus]
            nodes_to_update = nodes[0:-1]
            nodes_to_update.reverse()
            nodes_to_update = [u + J for u in nodes_to_update]
            updateShiftsInGraph(nodes_to_update)

        # update origin/first level of nodes
        for bus in bus_to_nodes:
            # the last ride of each bus is the end of all shifts
            last_ride = bus_to_nodes[bus][-1]
            G.node[last_ride]["S_end_time"] = G.node[last_ride]["end_time"]
            G.node[last_ride]["S_time_of_beginning_of_break"] = G.node[last_ride]["end_time"]
            G.node[last_ride]["S_price"] = 0
            G.node[last_ride]["S_neighbor"] = "target"

            # find shifts from all other rides
            nodes = bus_to_nodes[bus]
            nodes_to_update = nodes[0:-1]
            nodes_to_update.reverse()
            updateShiftsInGraph(nodes_to_update)

        # find the max paths
        neighbors = G["start"]
        S_price = [0] * J
        duration = [0] * J

        # get the price and duration of all available shifts
        for neighbor in neighbors:
            S_price[neighbor] = G.node[neighbor]["S_price"] + G["start"][neighbor]["weight"]
            duration[neighbor] = G.node[neighbor]["S_end_time"] - G.node[neighbor]["start_time"]

        max_value = max(S_price)
        max_nodes_to_begin = [idx for idx, v in enumerate(S_price) if v == max_value]

        # find the shortest shift
        # ---------------------------------------------- changed < to <= in line duration[neighbor] < min_duration -----------------------------------------------------------------------------------
        min_duration = 9 * 60
        path = [-1]
        for neighbor in max_nodes_to_begin:
            if duration[neighbor] <= min_duration:
                min_duration = duration[neighbor]
                path = [neighbor]

        while path[-1] is not "target":
            path += [G.node[path[-1]]["S_neighbor"]]

        return {"max_value": max_value, "path": path}

    # Main loop
    count = 0
    while True:

        count += 1
        print("Iteration #", count)
        if count > max_num_of_iter:
            print("Panic: got tired after {0} iterations".format(max_num_of_iter))
            print("\ngetting optimal solution up to now:")
            # sys.exit(-1)
            break

        max_shifts = getShifts(y)

        # ---------------------------------------------------------------------------------------------------------------

        print("Optimal solution value of the sub problem ", max_shifts["max_value"])

        if max_shifts["max_value"] > 1 + 1e-12:
            # if it did then create new column for the master problem based on the solution of the sub problem
            new_shift = max_shifts['path']
            # num_of_new_shifts = len(new_shifts)
            ez = [j % J for j in max_shifts['path'] if isinstance(j, int)]
            assert len(set(ez)) == len(ez), "somewhere it took a ride more then once in path"

            # for (k, i) in L:
            #     if z[L.index((k, i))] > 1e-6:
            #         ez.append(L.index((k, i)))

            c_master.variables.add(obj=[1], columns=[[ez, [1] * len(ez)]])
            # c_master.write("main.lp")
            # resolve master problem
            c_master.solve()

            if c_master.solution.get_status() != 1:  # code for optimal solution found
                print("Panic: cannot find feasible solution for the master problem")
                sys.exit(-1)

            print("Optimal solution value ", c_master.solution.get_objective_value())
            y = c_master.solution.get_dual_values()  # update dual solution

        else:  # if not - we are done
            break

    # print final fractional solution
    # x = c_master.solution.get_values()
    # for i in range(c_master.variables.get_num()):
    #     if x[i] > 1e-6:
    #         print(i, x[i])

    valid_lb = c_master.solution.get_objective_value()

    # *** resolve the model as an integer programming model ***

    # change the type of all the variables from continuous (default) to integer
    c_master.variables.set_types(zip(range(c_master.variables.get_num()), "I" * c_master.variables.get_num()))

    # add constraint to force not taking single trip routes
    # c_master.linear_constraints.add(lin_expr=A, senses="E" * J, rhs=[0] * J)
    # tup = zip(range(J), [original_obj_coefficients] * J)
    # c_master.objective.set_linear(tup)
    c_master.write("almost.lp")

    # note that zip is a python primitive function that convert to lists into list of tuples
    # e.g.   zip([1,2,3], ["a","b","c"])  -->   [(1,"a"), (2,"b"), (3,"c")]

    # the method Cplex.variables.get_num() returns the number of variables in the model

    # the method  Cplex.variables.set_types() change the type of the decision variables
    # its argument is a list of tuples, the first element of each tuple is the index of the variables and the second
    # a string that represent the type. The options are "I", "B", "C", "S", "N"
    # (for integer, binary, continuous, semi-continuous, semi-integer)

    # set a reasonable time limit for the solution time of the integer model (in seconds)
    # (hey we are not getting any younger over here)
    c_master.parameters.timelimit.set(max_seconds_of_final)
    c_master.solve()

    x = c_master.solution.get_values()
    drivers = []
    for i in range(c_master.variables.get_num()):
        if x[i] > 1e-6:
            drivers.append(i)
            print(i, x[i])

    # print final integer results
    results = []
    constraint_matrix = c_master.linear_constraints.get_rows()

    for ride in range(len(constraint_matrix)):
        # find shift
        current_available_shifts = constraint_matrix[ride].ind
        line_in_excel = current_available_shifts[0] + 1
        current_shift = list(set(current_available_shifts) & set(drivers))
        if (line_in_excel, current_shift[0]) not in results:
            results.append((line_in_excel, current_shift[0]))

    # results = list(set(results))
    c_master.write("myfinal.lp")  # uncomment to debug the model

    print('results: ' + str(results))

    print("_______________________________________________________________________")
    print("Best integer solution found", c_master.solution.get_objective_value(), "  Lower bound from LP relaxation ",
          valid_lb)
    print("number of patterns: ", len(drivers))

    with open(output_file_name + '_max_iter{0}_maxtime{1}.csv'.format(max_num_of_iter, max_seconds_of_final), 'wb') as csvfile:
        writer = csv.writer(csvfile)

        for line in results:
            writer.writerow([line[1]])

