import React from 'react';
import { Position } from 'reactflow';
import { Layers } from 'lucide-react';
import { BaseNode } from './BaseNode';
import { ErrorDisplay } from './ErrorDisplay';

const OpenFold2Node: React.FC<{ data: any }> = ({ data }) => {
  const content = (
    <div className="text-xs text-[hsl(var(--pc-text-muted))] space-y-1 pl-10">
      <div>Relax: {data.config?.relax_prediction ? 'Yes' : 'No'}</div>
      {data.error && <ErrorDisplay error={data.error} />}
    </div>
  );

  return (
    <BaseNode
      data={data}
      icon={Layers}
      label="OpenFold2"
      defaultLabel="OpenFold2"
      handles={[
        { type: 'target', position: Position.Left },
        { type: 'source', position: Position.Right },
      ]}
      content={content}
      defaultIconBg="bg-amber-100"
      defaultIconColor="text-amber-600"
    />
  );
};

export default OpenFold2Node;
