import { useMemo } from "react";
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from "reactflow";

import { shortHash } from "../lib/format";
import type { BuildTraceabilityResponse } from "../types";

interface TraceabilityGraphProps {
  traceability: BuildTraceabilityResponse;
}

export function TraceabilityGraph({ traceability }: TraceabilityGraphProps) {
  const { nodes, edges } = useMemo(() => buildGraph(traceability), [traceability]);

  return (
    <div className="traceability-graph" data-testid="traceability-graph">
      <ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.35} maxZoom={1.6} nodesDraggable={false}>
        <MiniMap pannable zoomable />
        <Controls showInteractive={false} />
        <Background gap={24} size={1} />
      </ReactFlow>
    </div>
  );
}

function buildGraph(traceability: BuildTraceabilityResponse): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [
    {
      id: "build",
      position: { x: 0, y: 0 },
      data: { label: `${traceability.product_id} / ${traceability.build_id}` },
      type: "input",
      className: "graph-node graph-node--build"
    }
  ];
  const edges: Edge[] = [];
  const rowGap = 86;
  const repoGap = 320;
  const commitGap = 240;
  const sideGap = 260;

  traceability.repositories.forEach((repository, repoIndex) => {
    const repoId = `repo-${repoIndex}`;
    const repoX = repoIndex * repoGap - ((traceability.repositories.length - 1) * repoGap) / 2;
    nodes.push({
      id: repoId,
      position: { x: repoX, y: rowGap },
      data: { label: repository.repository },
      className: "graph-node graph-node--repo"
    });
    edges.push({ id: `edge-build-${repoId}`, source: "build", target: repoId, animated: traceability.traceability_incomplete });

    repository.commits.forEach((commit, commitIndex) => {
      const commitId = `${repoId}-commit-${commit.hash}`;
      const commitX = repoX + (commitIndex % 3) * commitGap - commitGap;
      const commitY = rowGap * 2 + Math.floor(commitIndex / 3) * rowGap;
      nodes.push({
        id: commitId,
        position: { x: commitX, y: commitY },
        data: { label: shortHash(commit.hash, 12) },
        className: "graph-node graph-node--commit"
      });
      edges.push({ id: `edge-${repoId}-${commitId}`, source: repoId, target: commitId });

      commit.pull_requests.forEach((pullRequest, prIndex) => {
        const prId = `${commitId}-pr-${pullRequest.external_id}`;
        nodes.push({
          id: prId,
          position: { x: commitX - sideGap, y: commitY + prIndex * 54 },
          data: { label: `PR ${pullRequest.external_id}` },
          className: "graph-node graph-node--pr"
        });
        edges.push({ id: `edge-${commitId}-${prId}`, source: commitId, target: prId });
      });

      commit.issues.forEach((issue, issueIndex) => {
        const issueId = `${commitId}-issue-${issue.external_id}`;
        nodes.push({
          id: issueId,
          position: { x: commitX + sideGap, y: commitY + issueIndex * 54 },
          data: { label: issue.external_id },
          className: "graph-node graph-node--issue"
        });
        edges.push({ id: `edge-${commitId}-${issueId}`, source: commitId, target: issueId });
      });
    });
  });

  return { nodes, edges };
}
