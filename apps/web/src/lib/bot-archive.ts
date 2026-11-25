// Account-scoped IndexedDB. Private API responses never enter the service-worker cache.
type Entry = { id: string; as_of: string };
type Metadata<T> = { owner: string; cursor: number; snapshot: T; starred: string[] };

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("swan-bot-archive", 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore("insights", { keyPath: ["owner", "id"] }).createIndex("owner", "owner");
      request.result.createObjectStore("metadata", { keyPath: "owner" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function readArchive<T, I extends Entry>(owner: string) {
  const db = await open();
  try {
    return await new Promise<{ metadata?: Metadata<T>; insights: I[] }>((resolve, reject) => {
      const tx = db.transaction(["insights", "metadata"], "readonly");
      const records = tx.objectStore("insights").index("owner").getAll(owner);
      const metadata = tx.objectStore("metadata").get(owner);
      tx.oncomplete = () => resolve({ metadata: metadata.result, insights: records.result.map(row => row.value) });
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally { db.close(); }
}

export async function writeArchive<T, I extends Entry>(owner: string, updates: I[], metadata: Omit<Metadata<T>, "owner">) {
  const db = await open();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(["insights", "metadata"], "readwrite");
      for (const value of updates) tx.objectStore("insights").put({ owner, id: value.id, value });
      tx.objectStore("metadata").put({ owner, ...metadata });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally { db.close(); }
}

export async function clearArchive(owner: string) {
  const db = await open();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(["insights", "metadata"], "readwrite");
      const cursor = tx.objectStore("insights").index("owner").openCursor(IDBKeyRange.only(owner));
      cursor.onsuccess = () => { const row = cursor.result; if (row) { row.delete(); row.continue(); } };
      tx.objectStore("metadata").delete(owner);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally { db.close(); }
}
