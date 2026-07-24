import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveProject,
  createScenario,
  deleteProject,
  getDashboard,
  getProject,
  listProjects,
  listScenarios,
  restoreProject,
  updateProject,
} from "./client";
import type { CreateScenarioInput, ProjectListParams, UpdateProjectInput } from "./client";

export const workspaceKeys = {
  all: ["workspace"] as const,
  projects: () => [...workspaceKeys.all, "projects"] as const,
  projectList: (params: ProjectListParams) => [...workspaceKeys.projects(), "list", params] as const,
  project: (projectId: string) => [...workspaceKeys.projects(), "detail", projectId] as const,
  dashboard: () => [...workspaceKeys.all, "dashboard"] as const,
  reports: () => [...workspaceKeys.all, "reports"] as const,
  scenarios: (projectId: string) => [...workspaceKeys.project(projectId), "scenarios"] as const,
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

export function useCreateScenario(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateScenarioInput) => createScenario(projectId, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workspaceKeys.scenarios(projectId) }),
  });
}
