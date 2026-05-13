import type { Artifact, BuildComparisonResponse } from "../types";
import { artifactChecksum } from "./format";

export interface ArtifactDiff {
  added: Artifact[];
  removed: Artifact[];
  changed: { before: Artifact; after: Artifact }[];
  unchanged: Artifact[];
}

export function diffArtifacts(before: Artifact[], after: Artifact[]): ArtifactDiff {
  const beforeMap = new Map(before.map((a) => [a.name, a]));
  const afterMap = new Map(after.map((a) => [a.name, a]));

  const added: Artifact[] = [];
  const removed: Artifact[] = [];
  const changed: { before: Artifact; after: Artifact }[] = [];
  const unchanged: Artifact[] = [];

  for (const [name, afterArtifact] of afterMap) {
    const beforeArtifact = beforeMap.get(name);
    if (!beforeArtifact) {
      added.push(afterArtifact);
    } else if (artifactChecksum(beforeArtifact) !== artifactChecksum(afterArtifact)) {
      changed.push({ before: beforeArtifact, after: afterArtifact });
    } else {
      unchanged.push(afterArtifact);
    }
  }

  for (const [name, beforeArtifact] of beforeMap) {
    if (!afterMap.has(name)) {
      removed.push(beforeArtifact);
    }
  }

  return { added, removed, changed, unchanged };
}

export function comparisonToCsv(comparison: BuildComparisonResponse, artifactDiff: ArtifactDiff): string {
  const lines: string[] = ["Section,ID,Title,Detail"];

  for (const issue of comparison.unique_issues) {
    lines.push(`Issue,${issue.external_id},${issue.title ?? ""},${issue.status ?? ""}`);
  }

  for (const pr of comparison.unique_pull_requests) {
    lines.push(`PullRequest,${pr.external_id},${pr.title ?? ""},${pr.author ?? ""}`);
  }

  for (const commit of comparison.unique_commits) {
    lines.push(`Commit,${commit},,`);
  }

  for (const artifact of artifactDiff.added) {
    lines.push(`PackageAdded,${artifact.id},${artifact.name},${artifact.type}`);
  }

  for (const artifact of artifactDiff.removed) {
    lines.push(`PackageRemoved,${artifact.id},${artifact.name},${artifact.type}`);
  }

  for (const { after } of artifactDiff.changed) {
    lines.push(`PackageChanged,${after.id},${after.name},${after.type}`);
  }

  return lines.join("\n");
}
