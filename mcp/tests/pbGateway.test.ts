import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the pocketbase module so we can drive auth/operation behaviour.
const state = {
  authValid: false,
  authCalls: 0,
  getOne: vi.fn(),
};

vi.mock('pocketbase', () => {
  class FakePocketBase {
    authStore = {
      get isValid() {
        return state.authValid;
      },
    };
    autoCancellation() {}
    collection() {
      return {
        authWithPassword: vi.fn(async () => {
          state.authCalls += 1;
          state.authValid = true;
          return {};
        }),
        getOne: state.getOne,
      };
    }
  }
  return { default: FakePocketBase };
});

const { JoblandPocketBaseGateway } = await import('../src/pbGateway.js');

function makeGateway() {
  return new JoblandPocketBaseGateway({
    url: 'http://pb.test',
    adminEmail: 'admin@test',
    adminPassword: 'secret',
  });
}

describe('JoblandPocketBaseGateway auth handling', () => {
  beforeEach(() => {
    state.authValid = false;
    state.authCalls = 0;
    state.getOne.mockReset();
  });

  it('authenticates once for a successful operation', async () => {
    state.getOne.mockResolvedValue({ id: 'job_1' });
    const gw = makeGateway();

    await expect(gw.get('jobs', 'job_1')).resolves.toEqual({ id: 'job_1' });
    expect(state.authCalls).toBe(1);
  });

  it('re-authenticates and retries once when PocketBase returns 403', async () => {
    state.getOne
      .mockRejectedValueOnce(Object.assign(new Error('Forbidden'), { status: 403 }))
      .mockResolvedValueOnce({ id: 'job_1' });
    const gw = makeGateway();

    await expect(gw.get('jobs', 'job_1')).resolves.toEqual({ id: 'job_1' });
    expect(state.authCalls).toBe(2); // initial + forced re-auth
    expect(state.getOne).toHaveBeenCalledTimes(2);
  });

  it('does not retry on non-auth errors', async () => {
    state.getOne.mockRejectedValue(Object.assign(new Error('Not Found'), { status: 404 }));
    const gw = makeGateway();

    await expect(gw.get('jobs', 'missing')).rejects.toThrow('Not Found');
    expect(state.authCalls).toBe(1);
    expect(state.getOne).toHaveBeenCalledTimes(1);
  });
});
