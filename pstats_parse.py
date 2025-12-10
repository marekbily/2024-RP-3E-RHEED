import pstats

p = pstats.Stats('cprofile_out.txt')
p.sort_stats('cumulative').print_stats(10)