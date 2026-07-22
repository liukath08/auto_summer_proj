import logging

import easy_biologic as ebl
import easy_biologic.base_programs as ebp

logging.basicConfig( level = logging.DEBUG )

channels = [ 0, 1, 2, 3 ,7 ]
by_channel = False
params = { 
	'voltages':  [ 0, 1,2,-2,1,0 ],
	'durations': [ 2 ],
	'cycles': 4,
}

save_path = 'data/ca-limit'
if not by_channel:
	# file if saving individually
	save_path += '.csv'

bl = ebl.BiologicDevice( 'USB0' )
prg = ebp.CALimit( bl, params, channels=channels )

prg.run()
prg.save_data( save_path, by_channel = by_channel )