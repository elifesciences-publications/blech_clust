# Import stuff!
import numpy as np
import tables
import easygui
import sys
import os

# Ask for the directory where the hdf5 file sits, and change to that directory
dir_name = easygui.diropenbox()
os.chdir(dir_name)

# Look for the hdf5 file in the directory
file_list = os.listdir('./')
hdf5_name = ''
for files in file_list:
	if files[-2:] == 'h5':
		hdf5_name = files

# Open the hdf5 file
hf5 = tables.openFile(hdf5_name, 'r+')

# Grab the names of the arrays containing digital inputs, and pull the data into a numpy array
dig_in_nodes = hf5.listNodes('/digital_in')
dig_in = []
dig_in_pathname = []
for node in dig_in_nodes:
	dig_in_pathname.append(node._v_pathname)
	exec("dig_in.append(hf5.root.digital_in.%s[:])" % dig_in_pathname[-1].split('/')[-1])
dig_in = np.array(dig_in)

# Get the stimulus delivery times - take the end of the stimulus pulse as the time of delivery
dig_on = []
for i in range(len(dig_in)):
	dig_on.append(np.where(dig_in[i,:] == 1)[0])
change_points = []
for on_times in dig_on:
	changes = []
	for j in range(len(on_times) - 1):
		if np.abs(on_times[j] - on_times[j+1]) > 30:
			changes.append(on_times[j])
	try:
		changes.append(on_times[-1]) # append the last trial which will be missed by this method
	except:
		pass # Continue without appending anything if this port wasn't on at all
	change_points.append(changes)	

# Show the user the number of trials on each digital input channel, and ask them to confirm
check = easygui.ynbox(msg = 'Digital input channels: ' + str(dig_in_pathname) + '\n' + 'No. of trials: ' + str([len(changes) for changes in change_points]), title = 'Check and confirm the number of trials detected on digital input channels')
# Go ahead only if the user approves by saying yes
if check:
	pass
else:
	print "Well, if you don't agree, blech_clust can't do much!"
	sys.exit()

# Ask the user which digital input channels should be used for getting spike train data, and convert the channel numbers into integers for pulling stuff out of change_points
dig_in_channels = easygui.multchoicebox(msg = 'Which digital input channels should be used to produce spike train data trial-wise?', choices = ([path for path in dig_in_pathname]))
dig_in_channel_nums = []
for i in range(len(dig_in_pathname)):
	if dig_in_pathname[i] in dig_in_channels:
		dig_in_channel_nums.append(i)

# Ask the user which digital input channels should be used for conditioning the stimuli channels above (laser channels for instance)
lasers = easygui.multchoicebox(msg = 'Which digital input channels were used for lasers? Click clear all and continue if you did not use lasers', choices = ([path for path in dig_in_pathname]))
laser_nums = []
for i in range(len(dig_in_pathname)):
	if dig_in_pathname[i] in lasers:
		laser_nums.append(i)

# Ask the user for the pre and post stimulus durations to be pulled out, and convert to integers
durations = easygui.multenterbox(msg = 'What are the signal durations pre and post stimulus that you want to pull out', fields = ['Pre stimulus (ms)', 'Post stimulus (ms)'])
for i in range(len(durations)):
	durations[i] = int(durations[i])

# Make the spike_trains node in the hdf5 file if it doesn't exist, else move on
try:
	hf5.createGroup('/', 'spike_trains')
except:
	pass

# Get list of units under the sorted_units group. Find the latest/largest spike time amongst the units, and get an experiment end time (to account for cases where the headstage fell off mid-experiment)
units = hf5.listNodes('/sorted_units')
expt_end_time = 0
for unit in units:
	if unit.times[-1] > expt_end_time:
		expt_end_time = unit.times[-1]

# Go through the dig_in_channel_nums and make an array of spike trains of dimensions (# trials x # units x trial duration (ms))
for i in range(len(dig_in_channels)):
	spike_train = []
	for j in range(len(change_points[dig_in_channel_nums[i]])):
		# Skip the trial if the headstage fell off before it
		if change_points[dig_in_channel_nums[i]][j] >= expt_end_time:
			break
		# Otherwise run through the units and convert their spike times to milliseconds
		else:
			spikes = np.zeros((len(units), durations[0] + durations[1]))
			for k in range(len(units)):
				for l in range(durations[0] + durations[1]):
					spikes[k, l] = len(np.where((units[k].times[:]>=change_points[dig_in_channel_nums[i]][j] - (durations[0]-l)*30)*(units[k].times[:]< change_points[dig_in_channel_nums[i]][j] - (durations[0]-l-1)*30))[0])
					
		# Append the spikes array to spike_train 
		spike_train.append(spikes)
	# And add spike_train to the hdf5 file
	hf5.createGroup('/spike_trains', str.split(dig_in_channels[i], '/')[-1])
	spike_array = hf5.createArray('/spike_trains/%s' % str.split(dig_in_channels[i], '/')[-1], 'spike_array', np.array(spike_train))
	hf5.flush()

	# Make conditional stimulus array for this digital input if lasers were used
	if laser_nums:
		cond_array = np.zeros(len(change_points[dig_in_channel_nums[i]]))
		for j in range(len(change_points[dig_in_channel_nums[i]])):
			# Skip the trial if the headstage fell off before it
			if change_points[dig_in_channel_nums[i]][j] >= expt_end_time:
				break
			# Else run through the lasers and check if the lasers went off within 5 secs of the stimulus delivery time
			for laser in laser_nums:
				if np.sum(np.abs(np.array(change_points[laser]) - change_points[dig_in_channel_nums[i]][j]) <= 5*30000) > 0:
					cond_array[j] = 1
		# Write the conditional stimulus array to the hdf5 file
		laser_array = hf5.createArray('/spike_trains/%s' % str.split(dig_in_channels[i], '/')[-1], 'laser_array', cond_array)
		hf5.flush() 

hf5.close()
						



	



