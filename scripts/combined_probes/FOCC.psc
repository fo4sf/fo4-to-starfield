Scriptname FOCC Hidden Native
{The combined core's plugin bridge, B0 (docs/combined-core-cpp-port.md section 4; docs/spikes/combined-core-probes.md,
 section B0). One native, bound at load by the SFSE plugin FOCCPing.dll through CommonLibSF (sfse/FOCCPing, its own PR):
 Ping(v) answers v + 1. This stub only declares it, the way Starfield's own Game.psc declares its natives: the compiler
 needs the declaration and the VM binds the body when the plugin registers "FOCC" "Ping". With no plugin loaded the call
 is an unbound native: the VM reports it in Papyrus.0.log and the call yields 0, which FOCC_B0.Ping traces as got=0.
 Compiled on its own by make_combined_probe.py with FOCC_B0.psc (compile_b0.txt); packed only when both compile.}

int Function Ping(int v) global native
