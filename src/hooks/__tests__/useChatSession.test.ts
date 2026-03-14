import { describe, expect, it } from 'vitest';
import { getPaneForRestoredViewerVisibility } from '../useChatSession';

describe('getPaneForRestoredViewerVisibility', () => {
  it('returns viewer pane when viewer should be visible', () => {
    expect(getPaneForRestoredViewerVisibility(true)).toBe('viewer');
  });

  it('returns null pane when viewer should be hidden', () => {
    expect(getPaneForRestoredViewerVisibility(false)).toBeNull();
  });
});
