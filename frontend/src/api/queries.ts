import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveProject,
  archiveScenario,
  bulkProjectAction,
  bulkUpdatePersonas,
  compareScenarios,
  controlRun,
  createCustomPersona,
  createRun,
  createScenario,
  deleteProject,
  deleteScenario,
  duplicateProject,
  duplicateScenario,
  getDashboard,
  getProject,
  getProvenance,
  getRun,
  getRunEvents,
  getScenario,
  listEffectivePersonas,
  listProjects,
  listScenarios,
  putPersonaOverride,
  resetPersonaOverride,
  restoreScenario,
  restoreProject,
  submitGraphFeedback,
  updateScenario,
  updateProject,
} from "./client";
import type { ApiEffectivePersona, ApiPersonaDto, CreateScenarioInput, ProjectListParams, UpdateProjectInput, UpdateScenarioInput } from "./client";

export const workspaceKeys = {
  all: ["workspace"] as const,
  projects: () => [...workspaceKeys.all, "projects"] as const,
  projectList: (params: ProjectListParams) => [...workspaceKeys.projects(), "list", params] as const,
  project: (projectId: string) => [...workspaceKeys.projects(), "detail", projectId] as const,
  dashboard: () => [...workspaceKeys.all, "dashboard"] as const,
  reports: () => [...workspaceKeys.all, "reports"] as const,
  scenarios: (projectId: string) => [...workspaceKeys.project(projectId), "scenarios"] as const,
  scenario: (projectId: string, scenarioId: string) => [...workspaceKeys.scenarios(projectId), scenarioId] as const,
  personas: (projectId: string, scenarioId: string) => [...workspaceKeys.scenario(projectId, scenarioId), "personas"] as const,
  run: (runId: string) => [...workspaceKeys.all, "runs", runId] as const,
  runEvents: (runId: string, cursor?: string) => [...workspaceKeys.run(runId), "events", cursor ?? "start"] as const,
  provenance: (projectId: string) => [...workspaceKeys.project(projectId), "provenance"] as const,
};

export function useProjects(params: ProjectListParams = {}) {
  return useQuery({ queryKey: workspaceKeys.projectList(params), queryFn: () => listProjects(params) });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: workspaceKeys.project(projectId ?? ""),
    queryFn: () => getProject(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useDashboard() {
  return useQuery({ queryKey: workspaceKeys.dashboard(), queryFn: getDashboard });
}

export function useReports() {
  return useQuery({
    queryKey: workspaceKeys.reports(),
    queryFn: async () => {
      const projects = await listProjects({ status: "active", limit: 100 });
      return Promise.all(
        projects.items
          .filter((project) => project.report_available)
          .map((project) => getProject(project.id)),
      );
    },
  });
}

export function useScenarios(projectId: string | undefined) {
  return useQuery({
    queryKey: workspaceKeys.scenarios(projectId ?? ""),
    queryFn: () => listScenarios(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useScenario(projectId?: string, scenarioId?: string) {
  return useQuery({ queryKey: workspaceKeys.scenario(projectId ?? "", scenarioId ?? ""), queryFn: () => getScenario(projectId!, scenarioId!), enabled: Boolean(projectId && scenarioId) });
}

export function useEffectivePersonas(projectId?: string, scenarioId?: string) {
  return useQuery({ queryKey: workspaceKeys.personas(projectId ?? "", scenarioId ?? ""), queryFn: () => listEffectivePersonas(projectId!, scenarioId!) as Promise<{ items: ApiEffectivePersona[] }>, enabled: Boolean(projectId && scenarioId) });
}

export function useRun(runId?: string) {
  return useQuery({ queryKey: workspaceKeys.run(runId ?? ""), queryFn: () => getRun(runId!), enabled: Boolean(runId), refetchInterval: (query) => ["queued", "running", "paused"].includes(query.state.data?.status ?? "") ? 1500 : false });
}

export function useRunEvents(runId?: string, cursor?: string) {
  return useQuery({ queryKey: workspaceKeys.runEvents(runId ?? "", cursor), queryFn: () => getRunEvents(runId!, cursor), enabled: Boolean(runId), refetchInterval: 1500 });
}

export function useProvenance(projectId?: string) {
  return useQuery({ queryKey: workspaceKeys.provenance(projectId ?? ""), queryFn: () => getProvenance(projectId!), enabled: Boolean(projectId) });
}

function useProjectMutation<TInput>(mutationFn: (input: TInput) => Promise<unknown>, projectId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: workspaceKeys.projects() }),
        queryClient.invalidateQueries({ queryKey: workspaceKeys.dashboard() }),
        queryClient.invalidateQueries({ queryKey: workspaceKeys.reports() }),
        ...(projectId ? [queryClient.invalidateQueries({ queryKey: workspaceKeys.project(projectId) })] : []),
      ]);
    },
  });
}

export function useUpdateProject(projectId: string) {
  return useProjectMutation((input: UpdateProjectInput) => updateProject(projectId, input), projectId);
}

export function useArchiveProject() {
  return useProjectMutation((projectId: string) => archiveProject(projectId));
}

export function useRestoreProject() {
  return useProjectMutation((projectId: string) => restoreProject(projectId));
}

export function useDeleteProject() {
  return useProjectMutation((projectId: string) => deleteProject(projectId));
}

export function useDuplicateProject() {
  return useProjectMutation(({ id, name }: { id: string; name?: string }) => duplicateProject(id, { name }));
}

export function useBulkProjectAction() {
  return useProjectMutation((input: { project_ids: string[]; action: "archive" | "restore" | "delete" }) => bulkProjectAction(input));
}

export function useCreateScenario(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateScenarioInput) => createScenario(projectId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workspaceKeys.scenarios(projectId) }),
  });
}

function useScenarioMutation<TInput>(projectId: string, mutationFn: (input: TInput) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn, onSuccess: async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: workspaceKeys.scenarios(projectId) }),
      queryClient.invalidateQueries({ queryKey: workspaceKeys.project(projectId) }),
    ]);
  } });
}

export function useUpdateScenario(projectId: string, scenarioId: string) {
  return useScenarioMutation(projectId, (input: UpdateScenarioInput) => updateScenario(projectId, scenarioId, input));
}
export function useDuplicateScenario(projectId: string) {
  return useScenarioMutation(projectId, ({ scenarioId, name }: { scenarioId: string; name?: string }) => duplicateScenario(projectId, scenarioId, { name }));
}
export function useArchiveScenario(projectId: string) {
  return useScenarioMutation(projectId, (scenarioId: string) => archiveScenario(projectId, scenarioId));
}
export function useRestoreScenario(projectId: string) {
  return useScenarioMutation(projectId, (scenarioId: string) => restoreScenario(projectId, scenarioId));
}
export function useDeleteScenario(projectId: string) {
  return useScenarioMutation(projectId, (scenarioId: string) => deleteScenario(projectId, scenarioId));
}
export function useCompareScenarios(projectId: string) {
  return useMutation({ mutationFn: (scenarioIds: string[]) => compareScenarios(projectId, scenarioIds) });
}
export function usePersonaOverride(projectId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: ({ personaId, expected_version, base_environment_revision, patch }: { personaId: string; expected_version: number; base_environment_revision: number; patch: Partial<ApiPersonaDto> }) => putPersonaOverride(projectId, scenarioId, personaId, { expected_version, base_environment_revision, patch }), onSuccess: () => queryClient.invalidateQueries({ queryKey: workspaceKeys.personas(projectId, scenarioId) }) });
}
export function useResetPersona(projectId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: ({ personaId, expectedVersion }: { personaId: string; expectedVersion: number }) => resetPersonaOverride(projectId, scenarioId, personaId, expectedVersion), onSuccess: () => queryClient.invalidateQueries({ queryKey: workspaceKeys.personas(projectId, scenarioId) }) });
}
export function useCreateCustomPersona(projectId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (input: Omit<ApiEffectivePersona, "id" | "source"> & { expected_version: number }) => createCustomPersona(projectId, scenarioId, input), onSuccess: () => queryClient.invalidateQueries({ queryKey: workspaceKeys.personas(projectId, scenarioId) }) });
}
export function useBulkUpdatePersonas(projectId: string, scenarioId: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (input: { persona_ids: string[]; patch: Partial<ApiEffectivePersona>; expected_version: number }) => bulkUpdatePersonas(projectId, scenarioId, input), onSuccess: () => queryClient.invalidateQueries({ queryKey: workspaceKeys.personas(projectId, scenarioId) }) });
}
export function useGraphFeedback(projectId: string) {
  return useMutation({ mutationFn: (input: Parameters<typeof submitGraphFeedback>[1]) => submitGraphFeedback(projectId, input) });
}
export function useCreateRun(projectId: string, scenarioId: string) {
  return useMutation({ mutationFn: (expectedScenarioVersion: number) => createRun(projectId, scenarioId, { expected_scenario_version: expectedScenarioVersion }) });
}
export function useControlRun(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: ({ action, expectedVersion }: { action: "pause" | "resume" | "cancel"; expectedVersion: number }) => controlRun(runId, action, expectedVersion), onSuccess: (run) => queryClient.setQueryData(workspaceKeys.run(runId), run) });
}
