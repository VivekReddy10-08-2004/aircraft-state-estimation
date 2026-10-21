# **Research Proposal:**

## **Latency Aware Aircraft State Estimation: Comparing Extended Kalman Filters and Recurrent Neural Networks under Delayed Telemetry**

**Investigators:** Vivek Reddy Bhimavarapu, Grace Kalonji  
**Duration:** September 21, 2026 – December 1, 2026  
**Expected Commitment:** Approximately 4-5 hours per week per student

**Central Question**:

Under delayed and incomplete aircraft telemetry, when is a classical state estimator sufficient, and when does a learned sequence model provide enough additional accuracy to justify its added computational complexity?

## **Project Summary**

Real time aircraft tracking systems rely on telemetry that may arrive with delay, noise, and occasional missing observations. A tracking system may therefore receive information describing where an aircraft was several seconds ago rather than where it is at the present moment.

This project will study how different estimation methods recover an aircraft's current state from delayed telemetry.

We will compare a classical probabilistic estimator, the **Extended Kalman Filter (EKF)**, against two recurrent neural-network architectures, **GRU** and **LSTM**, using historical aircraft trajectory data. A simple constant-velocity dead-reckoning model will serve as a baseline.

The primary goal is to determine when additional model complexity provides a meaningful benefit. In particular, the study will examine whether learned sequence models become more accurate than an EKF as telemetry delay and packet loss increase, and whether any accuracy improvement is large enough to justify the additional computational cost.

## 

## 

## **Research Questions**

The project will address four primary questions:

1. How does aircraft position-estimation error change as telemetry delay increases?  
2. Do recurrent neural networks outperform an EKF under longer delays or nonlinear aircraft maneuvers such as turns, climbs, and descents?  
3. How robust are the different estimators when telemetry observations are intermittently missing?  
4. What tradeoff exists between estimation accuracy and per update inference latency?

The study will **not** assume that neural networks should outperform classical estimation methods. A result showing that the EKF remains more accurate or more computationally efficient would be equally meaningful.

## **Data and Experimental Setup**

Historical aircraft trajectory data will be obtained from the **OpenSky Network** or another publicly available aviation telemetry source.

Relevant variables include:

* position,  
* altitude,  
* ground speed,  
* heading,  
* vertical rate,  
* timestamps.

Geographic coordinates will be transformed into a local Cartesian coordinate system so that prediction errors can be measured directly in meters.

The benchmark will simulate degraded telemetry by injecting controlled network delay and packet loss.

Example delay conditions will include:

τ ∈ {0, 2, 5, 10, 15} seconds

with additional stochastic-delay experiments if time permits.

Packet-loss conditions may include:

p\_loss ∈ {0, 0.05, 0.10, 0.20}

All estimators will receive equivalent information at evaluation time. No model will have access to future telemetry.

## **Models**

Four estimation approaches will be evaluated.

### **Constant-Velocity Dead Reckoning**

A simple kinematic baseline that extrapolates the latest known aircraft position using observed velocity and heading.

### **Extended Kalman Filter**

A nonlinear probabilistic state estimator that propagates aircraft position and motion while maintaining an estimate of state uncertainty.

The filter will use a state representation containing position, speed, heading, altitude, and vertical motion.

### **GRU**

A recurrent neural network trained on short historical trajectory windows to predict the current aircraft state from delayed observations.

### **LSTM**

A second recurrent architecture using the same input and prediction task, allowing comparison between two common sequence-modeling approaches.

The scope will intentionally remain limited to these four methods to ensure that the benchmark is rigorous and achievable within the proposed timeline.

## **Evaluation**

The primary performance metric will be horizontal position error in meters.

Additional metrics will include:

* altitude error,  
* velocity error,  
* mean and median inference latency,  
* 95th-percentile inference latency,  
* robustness under different packet-loss levels,  
* performance during straight flight versus maneuvering flight.

The final analysis will include plots such as:

* position RMSE versus telemetry delay,  
* position error versus packet loss,  
* inference latency by model,  
* trajectory overlays comparing predicted and true paths,  
* error heatmaps across delay and packet-loss conditions.

## 

## **Project Timeline**

#### **Weeks 1–2: Data Pipeline & Baseline Construction**

* Retrieve and clean real-world flight trajectory data.  
* Standardize timestamps, aircraft tracks, and telemetry fields.  
* Convert latitude/longitude/altitude into an appropriate Cartesian or local coordinate representation for modeling.  
* Construct fixed-length trajectory windows and train/validation/test partitions.  
* Implement and validate constant-velocity / kinematic dead-reckoning baselines.  
* Define the reproducible experiment pipeline and initial evaluation metrics.

  #### **Weeks 3–4:State-Space Modeling**

* Formulate the aircraft state representation and motion model.  
* Implement the Extended Kalman Filter (EKF).  
* Validate state transitions, measurement updates, and covariance propagation.  
* Perform sanity checks under clean and mildly delayed observations.  
* Establish EKF performance as the primary probabilistic filtering baseline.  
* Analyze uncertainty calibration and failure cases.

  #### **Weeks 5–6: Recurrent Neural Sequence Models**

* Implement GRU- and LSTM-based trajectory estimators.  
* Incorporate observation age / packet-delay information directly into the sequence-model inputs.  
* Train models using identical trajectory partitions for fair comparison.  
* Tune major architectural and optimization parameters.  
* Evaluate sequence models against dead reckoning and EKF under nominal network conditions.  
* Analyze learned-model sensitivity to trajectory length and observation history.

  #### **Weeks 7–8: Controlled Network-Degradation Experiments**

* Develop a reproducible simulation framework for:  
  * stochastic packet latency,  
  * increasing observation age,  
  * packet loss,  
  * burst loss,  
  * irregular sampling.  
* Evaluate EKF, GRU, LSTM, and dead-reckoning performance across controlled degradation levels.  
* Measure position error, velocity/state-estimation error, robustness, and recovery behavior.  
* Identify operating regimes in which classical and learned approaches outperform one another.

  #### **Weeks 9–10: Robustness, Ablation & Systems Analysis**

* Conduct ablation studies to isolate the value of:  
  * delay-awareness,  
  * historical sequence context,  
  * covariance modeling,  
  * model complexity.  
* Test model sensitivity across different aircraft trajectories, flight phases, and trajectory lengths where supported by the dataset.  
* Profile inference latency, throughput, memory usage, and computational cost.  
* Compare predictive accuracy against real-time deployment requirements.  
* Analyze accuracy–latency–complexity tradeoffs between probabilistic and neural approaches.  
* Run statistical significance or confidence-interval analysis where appropriate.

  #### **November 30–December 1**

* Consolidate experimental results and figures.  
* Produce comparative tables and robustness curves.  
* Document methodology and reproducibility procedures.  
* Complete the technical report.  
* Clean and publish the benchmark repository.  
* Summarize limitations, practical deployment implications, and directions for future work.

## **Division of Responsibilities:**

Both investigators will participate in experimental design, interpretation of results, and final editing.

## **Expected Outcomes**

The project will produce:

* a reproducible benchmark repository,  
* implementations of four aircraft-state estimators,  
* a documented telemetry-delay simulation framework,  
* quantitative comparison of estimation accuracy and computational cost,  
* a technical research report,  
* a short final presentation.

The expected research contribution is a practical comparison between model based probabilistic estimation and learned temporal prediction under controlled telemetry degradation.

\- 

Question 27: 17/25 (68%)

Feedback:

