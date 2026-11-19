// A new object for each node lifetime: a late callback from the old deployment
// must keep its stopped state even after the replacement node initializes.
context.set("logfireSaveState", { saving: false, stopping: false });
