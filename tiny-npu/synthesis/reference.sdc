# Reference constraints only: confirm library units/PVT and actual IO budgets.
# No clock/timing-closure claim can be made without real libraries + mapping.
create_clock -name core -period 1.000 [get_ports clk]
set_clock_uncertainty 0.100 [get_clocks core]
set_input_delay -clock core 0.100 [get_ports {reset in_valid out_ready a* b* c*}]
set_output_delay -clock core 0.100 [get_ports {in_ready out_valid result*}]
