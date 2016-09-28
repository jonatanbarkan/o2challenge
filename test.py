import twocars
import onecar

max_num_of_iter = 1000
max_seconds_of_final = 300
input_file_name = "large_data_csv.csv"
max_car_num = 1
stable = False

if max_car_num == 1:
    output_file_name = "{0}cars".format(max_car_num)
    onecar.run(max_num_of_iter, max_seconds_of_final, input_file_name, output_file_name, stable=stable)
elif max_car_num == 2:
    output_file_name = "{0}cars".format(max_car_num)
    twocars.run(max_num_of_iter, max_seconds_of_final, input_file_name, output_file_name, stable=stable)
