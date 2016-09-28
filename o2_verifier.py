# -------------------------------------------------------------------------------
# Name:        Verifier for the O^2 Challenge problem
#
# Author:      Tal Raviv, Niv Sarig
#
# Created:     08/01/2016
# Copyright:   (c) Tal Raviv 2016
# Licence:     Free
# -------------------------------------------------------------------------------

import csv
import sys



# Global variables
iDutyID = 0
iVeID = 1
iStartTime = 2
iEndTime = 3
iOrig = 4
iDest = 5
iLineNumber = 6


def print_welcome_msg():
    print "=================================================================================="
    print " Solution verifier for the O^2 Challenge"
    print " Please report bugs to talraviv69@gmail.com"
    print "=================================================================================="
    print " We will run the verifier with the orignal input file that we published so if you"
    print " sorted it be sure to check your solution with the original file"
    print "=================================================================================="
    print ' Usage: "python o2_verifier.py <input_file_name> <output_file_name>"'
    print " Make sure to include the .csv extention"
    print " The output file (your solution) must contain one value in each row"
    print ' (The first row may contain the string "Duty id")'
    print "=================================================================================="


def time_format(n):
    minutes = str(int(n) % 60)
    if len(minutes) == 1:
        minutes = '0' + minutes
    return str(int(n)/60)+":" + minutes


class Duty:
    def __init__(self, duty_id, duty_name):
        self.DutyId = duty_id
        self.duty_name = duty_name
        self.StartTime = None
        self.EndTime = None
        self.LastBreak = None
        self.Orig = None
        self.Dest = None
        self.VehicleIdsInDuty = set()
        self.ChangeoverCount = 0

    def non_consecutive_in_vehicle(self, vehicle):
        non_consecutivity_counter = 0
        duty_id = self.DutyId
        duty_ids_in_vehicle = list(vehicle.DutyIdsInVehicle)
        first_index = duty_ids_in_vehicle.index(duty_id)
        while True:
            try:
                next_index = duty_ids_in_vehicle.index(duty_id)
                for j in range(next_index + 1):
                    duty_ids_in_vehicle[j] = -1
                if next_index > first_index + 1:
                    non_consecutivity_counter += 1
                    previous_duty_name = duty_ids_map[vehicle.DutyIdsInVehicle[next_index - 1]]
                    print "Driver on Duty", duty_ids_map[duty_id], "gets off from vehicle", \
                        vehicle.name, "and on again after driver of Duty", previous_duty_name
                first_index = next_index
            except (ValueError, IndexError, KeyError):
                return non_consecutivity_counter


class Vehicle:
    def __init__(self, vehicle_id, vehicle_name):
        self.VehicleID = vehicle_id
        self.name = vehicle_name
        self.DutyIdsInVehicle = []


def check_duties(data):
    lErrorFlag = False
    vehicles = {}
    duties = {}
    data_lines = range(len(data))
    # Generate all vehicles and duties
    for i in data_lines:
        vehicles[data[i][iVeID]] = Vehicle(data[i][iVeID], vehicle_ids_map[data[i][iVeID]])
        duties[data[i][iDutyID]] = Duty(data[i][iDutyID], duty_ids_map[data[i][iDutyID]])

    # Sort by Vehicle ID and then by StartTime
    data = sorted(data, key=lambda a: a[iVeID]*1800+a[iStartTime])
    # Update duty ids in vehicles and vehicle ids in duties
    for i in data_lines:
        vehicles[data[i][iVeID]].DutyIdsInVehicle.append(data[i][iDutyID])

    # Sort by DutyID and then by StartTime
    data = sorted(data, key=lambda a: a[iDutyID]*1800+a[iStartTime])
    # Update vehicle ids in duties
    for i in data_lines:
        duties[data[i][iDutyID]].VehicleIdsInDuty.add(data[i][iVeID])

    # Vehicle switch check
    for duty in duties.itervalues():
        duty.ChangeoverCount = len(duty.VehicleIdsInDuty) - 1
        for vehicle_id in duty.VehicleIdsInDuty:
            vehicle = vehicles[vehicle_id]
            duty.ChangeoverCount += duty.non_consecutive_in_vehicle(vehicle)

        if duty.ChangeoverCount > 1:
            print "Driver on Duty", duty_ids_map[duty.DutyId], "drives on", len(duty.VehicleIdsInDuty), "vehicles"
            # A driver switches vehicles more than once
            print "Driver on Duty", duty_ids_map[duty.DutyId], "switches vehicles More than once"
            lErrorFlag = True

    for i in data_lines:

        CurrDuty = data[i][iDutyID]

        if i == 0 or CurrDuty != data[i-1][iDutyID]:
            duties[CurrDuty].StartTime = data[i][iStartTime]
            duties[CurrDuty].Orig = data[i][iOrig]
            duties[CurrDuty].LastBreak = data[i][iStartTime]

            if i > 0:
                duties[data[i-1][iDutyID]].EndTime = data[i-1][iEndTime]
                duties[data[i-1][iDutyID]].Dest = data[i-1][iDest]

        if i > 0 and CurrDuty == data[i - 1][iDutyID]:
            # Check changeover location legality
            if data[i][iOrig] != data[i-1][iDest]:
                    print "Error in line", data[i][iLineNumber], ": Duty", CurrDuty, "skips from destination terminal ",\
                        data[i-1][iDest], " to origin terminal", data[i][iOrig]
                    lErrorFlag = True

            # Check current start time >= previous end time
            if data[i][iStartTime] < data[i-1][iEndTime]:
                print "Error in line", data[i][iLineNumber], ": Duty", CurrDuty, "starts trip at time ", \
                    time_format(data[i][iStartTime]), " before the end of the previous trip at time", \
                    time_format(data[i - 1][iEndTime])
                lErrorFlag = True

            # Reset work without a break
            if data[i][iStartTime] - 30 >= data[i-1][iEndTime]:
                duties[CurrDuty].LastBreak = data[i][iStartTime]

            # Check breaks are legall
                if data[i][iEndTime] - duties[CurrDuty].LastBreak > 240:
                    print "Error in line ", data[i][iLineNumber], ": Duty", CurrDuty, \
                        "more than four hours without a break at the trip that ends at", time_format((data[i][iEndTime]))
                    lErrorFlag = True

        # Handle last record
        if i == len(data)-1:
            duties[CurrDuty].EndTime = data[i][iEndTime]
            duties[CurrDuty].Dest = data[i][iDest]

    return lErrorFlag, duties


def calculate_objective(lErrorFlag, duties):
    # Calculate objective function and find duties that exceed 9 hours.
    total_time = 0
    for i, d in duties.iteritems():
        if d.EndTime - d.StartTime > 9 * 60:
            print "Duty ", d.duty_name, "exceed 9 hours limit"
            lErrorFlag = True
        total_time += d.EndTime - d.StartTime
        if d.Orig != 99999 and d.Orig != 1:
            total_time += 30
        if d.Dest != 99999 and d.Dest != 1:
            total_time += 30


    print("Number of duties: ", len(duties))
    print "Total time and penalties (secondary objective function) ", total_time, "minutes (", time_format(total_time), \
        " hours)"
    if lErrorFlag:
        print "=================================================================================="
        print "Errors were found, your solution is unacceptable!!!"
    else:
        print "=================================================================================="
        print "No errors were found, your solution is acceptable!"


def get_data(args):
    print_welcome_msg()

    if len(args) != 3:

        print "=================================================================================="
        print "Wrong number of command line parameters"
        quit()

    data = []
    try:
        with open(args[1], 'rb') as csvfile:
            rows = csv.reader(csvfile, delimiter=',')
            for row in rows:
                if row[0] != "Duty id":  # skip first row
                    ez = row[3].split(":")
                    StartTime = int(ez[0])*60+int(ez[1])
                    ez = row[4].split(":")
                    EndTime = int(ez[0])*60+int(ez[1])
                    data.append([0, row[1], StartTime, EndTime, int(row[5]), int(row[7]), 0])
    except IOError as e:
        print "I/O error with input file '{2}' ({0}): {1}".format(e.errno, e.strerror, sys.argv[1])
        quit()

    vehicle_ids = {d[1] for d in data}
    vehicle_ids_map = {v_id: i for i, v_id in enumerate(vehicle_ids)}

    new_vehicle_ids = [vehicle_ids_map[d[1]] for d in data]
    for d, vehicle_id in zip(data, new_vehicle_ids):
        d[1] = vehicle_id

    vehicle_ids_map = {i: v_id for v_id, i in vehicle_ids_map.iteritems()}

    i = 0
    try:
        with open(args[2], 'rb') as csvfile:
            rows = csv.reader(csvfile, delimiter=',')
            for row in rows:
                if row[0] != "Duty id":  # skip first row
                    if i >= len(data):
                        print "Error: The number of entries in the input file is smaller than the " \
                              "number of entries in the output file"
                        quit()

                    data[i][iDutyID] = row[0]
                    data[i][iLineNumber] = i+1
                    i += 1
    except IOError as e:
        print "I/O error with the output file '{2}' ({0}): {1}".format(e.errno, e.strerror, sys.argv[2])
        quit()

    if len(data) > i:
        print "Error: The number of entries in the input file is larger than the number of entries in the output file"
        quit()

    duty_ids = {d[0] for d in data}
    duty_ids_map = {d_id: i for i, d_id in enumerate(duty_ids)}

    new_duty_ids = [duty_ids_map[d[0]] for d in data]
    for d, duty_id in zip(data, new_duty_ids):
        d[0] = duty_id

    duty_ids_map = {i: d_id for d_id, i in duty_ids_map.iteritems()}

    return data, vehicle_ids_map, duty_ids_map


data, vehicle_ids_map, duty_ids_map = get_data(sys.argv)
calculate_objective(*check_duties(data))
