"use client";

import React, { useState } from "react";
import { Folder, FolderOpen, FileCode, ChevronRight, ChevronDown } from "lucide-react";

interface FileNode {
  id: string;
  name: string;
  path: string;
  type: "file" | "directory";
  language?: string;
  size?: number;
  children?: FileNode[];
}

interface DirectoryTreeProps {
  nodes: FileNode[];
  onSelectFile: (node: FileNode) => void;
  selectedFileId?: string;
}

export function DirectoryTree({ nodes, onSelectFile, selectedFileId }: DirectoryTreeProps) {
  return (
    <div className="space-y-1 select-none text-sm text-slate-300 font-mono">
      {nodes.map((node) => (
        <TreeNode 
          key={node.id} 
          node={node} 
          onSelectFile={onSelectFile} 
          selectedFileId={selectedFileId} 
          depth={0} 
        />
      ))}
    </div>
  );
}

function TreeNode({ 
  node, 
  onSelectFile, 
  selectedFileId, 
  depth 
}: { 
  node: FileNode; 
  onSelectFile: (node: FileNode) => void; 
  selectedFileId?: string; 
  depth: number;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const isDirectory = node.type === "directory";
  const isSelected = selectedFileId === node.id;

  const handleClick = () => {
    if (isDirectory) {
      setIsOpen(!isOpen);
    } else {
      onSelectFile(node);
    }
  };

  return (
    <div className="flex flex-col">
      <div
        onClick={handleClick}
        style={{ paddingLeft: `${depth * 12}px` }}
        className={`flex items-center gap-2 py-1.5 px-2 rounded-md cursor-pointer hover:bg-slate-900/50 hover:text-slate-100 transition-colors ${
          isSelected ? "bg-purple-600/10 text-purple-400 font-semibold border border-purple-500/10" : ""
        }`}
      >
        {isDirectory ? (
          <>
            <span className="text-slate-500">
              {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            </span>
            <span className="text-purple-400">
              {isOpen ? <FolderOpen className="h-4.5 w-4.5 fill-purple-400/10" /> : <Folder className="h-4.5 w-4.5 fill-purple-400/10" />}
            </span>
          </>
        ) : (
          <>
            <span className="w-3.5 h-3.5" /> {/* empty space for chevron alignment */}
            <span className="text-indigo-400">
              <FileCode className="h-4.5 w-4.5" />
            </span>
          </>
        )}
        <span className="truncate">{node.name}</span>
      </div>

      {isDirectory && isOpen && node.children && (
        <div className="flex flex-col mt-0.5">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              onSelectFile={onSelectFile}
              selectedFileId={selectedFileId}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
