//! Search accounting, not a proof of complete legal-action enumeration.
//!
//! Each parallel actor-order invocation owns its counters. Reduction happens
//! in input order; retained top-K plans share one solve's aggregate audit.

use serde::Serialize;

#[derive(Clone, Debug, Default, Serialize)]
pub struct SearchAudit {
    pub budget_seconds: Option<f64>,
    pub action_limit_per_actor: Option<usize>,
    pub passes_executed: u64,
    pub order_passes_scheduled: u64,
    pub order_passes_started: u64,
    pub order_passes_completed: u64,
    /// Recursive entries admitted by the existing deadline guard.
    pub nodes_visited: u64,
    pub terminal_plans_evaluated: u64,
    /// Generated candidates, not the complete original-game legal action set.
    pub actions_generated: u64,
    pub action_limit_pruned: u64,
    pub disabled_actions_filtered: u64,
    /// Encountered deadline aborts, not the number of unknown omitted branches.
    pub deadline_cutoffs: u64,
}

impl SearchAudit {
    pub fn merge(&mut self, other: &Self) {
        self.passes_executed += other.passes_executed;
        self.order_passes_scheduled += other.order_passes_scheduled;
        self.order_passes_started += other.order_passes_started;
        self.order_passes_completed += other.order_passes_completed;
        self.nodes_visited += other.nodes_visited;
        self.terminal_plans_evaluated += other.terminal_plans_evaluated;
        self.actions_generated += other.actions_generated;
        self.action_limit_pruned += other.action_limit_pruned;
        self.disabled_actions_filtered += other.disabled_actions_filtered;
        self.deadline_cutoffs += other.deadline_cutoffs;
    }

    pub fn retained_candidate_tree_exhausted(&self) -> bool {
        self.order_passes_scheduled > 0
            && self.order_passes_completed == self.order_passes_scheduled
            && self.deadline_cutoffs == 0
    }
}
