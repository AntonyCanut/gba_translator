module.exports = {
  readFile: function() { throw new Error('fs.readFile not available in browser'); },
  writeFile: function() { throw new Error('fs.writeFile not available in browser'); }
};
