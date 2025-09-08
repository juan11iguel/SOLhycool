# Data Driven from First Principles

This folder contains resources, scripts, and documentation for integrating data-driven methods with first-principles modeling. The goal is to leverage machine learning and statistical techniques alongside physics-based models to enhance predictive accuracy and insight.

## Folder files

- `evaluate_model_dc` — Code for evaluating the first principles model of ACHE developed by Elche people. It requires `dc_in.csv` data, which includes the inputs (Tamb, Tdcin, q_dc, wfan) to be evaluated.
- `evaluate_model_wct` — Code for evaluating the first principles model of WCT developed by Elche people. It requires `wct_in.csv` data, which includes the inputs (Tamb, H, Twctin, q_wct, wct_fan) to be evaluated.
- `dc_out.csv` — This is the ouptut generated when `evaluate_model_dc` is executed.
- `wct_out.csv` — This is the ouptut generated when `evaluate_model_wct` is executed.
- `README.md` — This documentation.

## Usage

1. **Create a dataset of inputs:**
    The input dataset must cover the whole operating range and with enough variability. This is done using the...Juanmi...
    > [!warning] Very large model files
    > Note that including a very large number of points in your dataset can result in model files that are extremely large (several megabytes in size).

2. **Run evaluation of physical models:**
    The script `evaluate_model_xx` must be executed
    ``` 
    Take in mind that if your input csv contains a dataset of 2000 points to be evaluated (rows), the execution time of this script can be up to 20 minutes (depending on your computer's performance).

3. **Check the final values:**
    Although `evaluate_model_xx` eliminates NaN numbers generated when the first principles model fails, it is important to visualize the final outputs to manually eliminate non-physical model outputs(for example negative values).
     ```
     In case you eliminate rows, don't forget to save manually the table: `writetable(wct_out_sinnan, "wct_out.csv");` 

4. **Train one or multiple ML alternatives:**   
    Using the `batch_training.m` script, one can generate different data-driven models using the data generated with the evaluation of the physical models. To call it a convenience script is used, `generate_data_driven_models.m`, by running the appropiate section.
