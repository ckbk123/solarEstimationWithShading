import pandas as pd
import numpy as np
from colorama import Fore, Style
import matplotlib.pyplot as plt
from datetime import datetime

def state_of_charge_estimation(final_irradiance, time_array, solar_peak, conv_eff, conv_max, charge_eff, discharge_eff, max_soc, min_soc, batt_nom_cap, batt_nom_volt):
    print(f'{Fore.YELLOW}Computing the estimated evolution of the system state of charge...{Style.RESET_ALL}')
    # construct the consumption profile
    raw_consumption = pd.read_excel('./SystemData/Consumption_Profile.xlsx', index_col = None)
    consumption_over_time = np.zeros(len(time_array))

    # copy the raw consumption over to consumption over time
    for i in range(0,len(raw_consumption)):
        consumption_over_time[np.where(time_array.hour == raw_consumption['Hour of day'][i])] = raw_consumption['Consumption (Wh)'][i]

    # we determine the energy flow to OR from the battery by taking the energy generated by the converter minus the consumption
    # if this is positive, it means battery is getting some energy in
    # if this is negative, it means that the battery must be supplying energy
    energy_out_of_converter = final_irradiance * solar_peak * conv_eff/(1000*100)
    energy_out_of_converter[energy_out_of_converter > conv_max] = conv_max
    energy_flow_to_from_battery = energy_out_of_converter - consumption_over_time
    soc_evolution = np.zeros(len(time_array))
    soc_evolution[0] = max_soc

    for i in range(1, len(time_array)):
        # in case there is excess energy
        if (energy_flow_to_from_battery[i] >= 0):
            soc_evolution[i] = soc_evolution[i - 1] + energy_flow_to_from_battery[i] * (charge_eff/100) * 100 / (batt_nom_cap * batt_nom_volt)
        else:
            soc_evolution[i] = soc_evolution[i - 1] + energy_flow_to_from_battery[i] * 100 / (batt_nom_cap * batt_nom_volt * (discharge_eff/100))

        # clamp the system down to soc limits
        if (soc_evolution[i] > max_soc):
            soc_evolution[i] = max_soc
        elif (soc_evolution[i] < min_soc):
            soc_evolution[i] = min_soc

    print(f'{Fore.GREEN}Done!{Style.RESET_ALL}')

    print(f'{Fore.YELLOW}Saving the time series, hourly SOC, hourly energy flow, hourly consumption, and hourly irradiation to Excel file, also a figure of hourly SOC and irradiation, in DebugData{Style.RESET_ALL}')
    # this section write the data to an Excel so that the user could manipulate if they want to
    debug_data = pd.DataFrame({'Time': time_array.tz_localize(None), 'SOC': soc_evolution, 'Energy flow': energy_flow_to_from_battery, 'Consumption': consumption_over_time,
         'Irradiation': final_irradiance}).set_index('Time')

    ok_to_write = 0
    while (ok_to_write == 0):
        try:
            debug_data.to_excel('./DebugData/soc_ev.xlsx')
            ok_to_write = 1
        except:
            input(f"{Fore.RED}It seems soc_ev.xlsx is opened, you should close it then hit ENTER so that the program can retry writing to file...{Style.RESET_ALL}")

    # plot a simple graph to display the hourly irradiation and SOC
    plt.rcParams.update({'font.size': 8})
    fig, ax = plt.subplots()

    # add first line to plot
    ax.step(time_array, final_irradiance, color='orange', linewidth=2)
    # add x-axis label
    ax.set_xlabel('Time', fontsize=14)
    ax.set_xlim([time_array[0], time_array[-1]])
    # add y-axis label
    ax.set_ylabel('Hourly solar irradiation (Whm-2)', color='orange', fontsize=16)
    ax.set_ylim([0, 1000])

    # define second y-axis that shares x-axis with current plot
    ax2 = ax.twinx()

    # add second line to plot
    ax2.step(time_array, soc_evolution, color='blue', linewidth=2)
    ax2.set_ylim([0, 100])
    # add second y-axis label
    ax2.set_ylabel('Hourly state of charge (%)', color='blue', fontsize=16)
    plt.savefig('./DebugData/hourly_soc_estimation_from_user_visual.png')
    print(f'{Fore.GREEN}Done!{Style.RESET_ALL}')
    print(f'{Fore.LIGHTCYAN_EX}Close figure to continue...{Style.RESET_ALL}')
    plt.grid()
    plt.show()

    minimum_soc_throughout = np.min(soc_evolution)
    if (minimum_soc_throughout > min_soc):
        print(f"{Fore.LIGHTGREEN_EX}Min SOC throughout observation period is " + str(round(minimum_soc_throughout, 2)) +
                               "% which is higher than the minimum SOC of " +
                               str(min_soc) + f"%\nSo the system COULD OPERATE CONTINUOUSLY!{Style.RESET_ALL}")
        f = open(datetime.now().strftime("%m-%d-%Y-%H-%M-%S") + "-verdict" + ".txt", "w")
        f.write("Min SOC throughout observation period is " + str(round(minimum_soc_throughout, 2)) +
                               "% which is higher than the minimum SOC of " +
                               str(min_soc) + "%\nSo the system COULD OPERATE CONTINUOUSLY!")

    else:
        print(f"{Fore.LIGHTRED_EX}Min SOC throughout observation period is " + str(round(minimum_soc_throughout, 2)) +
                               "% which is equal to the minimum SOC of " +
                               str(min_soc) + f"%\nSo the system MAY NOT OPERATE CONTINUOUSLY!{Style.RESET_ALL}")

        f = open(datetime.now().strftime("%m-%d-%Y-%H-%M-%S") + "-verdict" + ".txt", "w")
        f.write("Min SOC throughout observation period is " + str(round(minimum_soc_throughout, 2)) +
                               "% which is equal to the minimum SOC of " +
                               str(min_soc) + "%\nSo the system MAY NOT OPERATE CONTINUOUSLY!")
