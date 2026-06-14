let currentUser = null;
let fetchPromise = null;

export async function getCurrentUser() {
  if (currentUser) {
    return currentUser;
  }

  if (fetchPromise) {
    return fetchPromise;
  }

  fetchPromise = (async () => {
    try {
      const response = await fetch("/api/users/me");

      if (response.ok) {
        currentUser = await response.json();
        return currentUser;
      }

      return null;
    } catch (error) {
      console.error("Error fetching current user:", error);
      return null;
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

export async function logout() {
  try {
    await fetch("/api/users/logout", {
        method: "POST"
    });
  } catch (error) {
    console.error("Error during server logout:", error);
  } finally {
    currentUser = null;
    window.location.href = "/";
  }
}