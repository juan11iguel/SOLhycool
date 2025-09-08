The procedure to scale the base physical models is the following:

1. Define operating ranges for each component: DC, SC (WCT programatically scalable). Usually just the flow range changes.
2. Evaluate the `scale_models.m` script which generates the updated parameters (i.e., number of parallel DC systems, and surface and number of pipes for the condenser)
3. When calling any of the component functions or the combined cooler, remember to provide both the updated limits and the scaled parameters.

NOTE: For the dry cooler, the only limit that changes, the flow, is automatically scaled with the number of DCs in parallel, so there is no need to scale it.