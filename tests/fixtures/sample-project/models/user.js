class User {
  constructor(id, name, email) {
    this.id = id;
    this.name = name;
    this.email = email;
  }

  static async findAll() {
    return [
      new User(1, 'Alice', 'alice@example.com'),
      new User(2, 'Bob', 'bob@example.com'),
    ];
  }

  static async findById(id) {
    const users = await User.findAll();
    return users.find(u => u.id === id) || null;
  }
}

module.exports = User;
