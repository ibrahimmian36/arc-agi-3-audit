// Dafny program ls20_level2.dfy compiled into JavaScript
// Copyright by the contributors to the Dafny Project
// SPDX-License-Identifier: MIT

const BigNumber = require('bignumber.js');
BigNumber.config({ MODULO_MODE: BigNumber.EUCLID })
let _dafny = (function() {
  let $module = {};
  $module.areEqual = function(a, b) {
    if (typeof a === 'string' && b instanceof _dafny.Seq) {
      // Seq.equals(string) works as expected,
      // and the catch-all else block handles that direction.
      // But the opposite direction doesn't work; handle it here.
      return b.equals(a);
    } else if (typeof a === 'number' && BigNumber.isBigNumber(b)) {
      // This conditional would be correct even without the `typeof a` part,
      // but in most cases it's probably faster to short-circuit on a `typeof`
      // than to call `isBigNumber`. (But it remains to properly test this.)
      return b.isEqualTo(a);
    } else if (typeof a !== 'object' || a === null || b === null) {
      return a === b;
    } else if (BigNumber.isBigNumber(a)) {
      return a.isEqualTo(b);
    } else if (a._tname !== undefined || (Array.isArray(a) && a.constructor.name == "Array")) {
      return a === b;  // pointer equality
    } else {
      return a.equals(b);  // value-type equality
    }
  }
  $module.toString = function(a) {
    if (a === null) {
      return "null";
    } else if (typeof a === "number") {
      return a.toFixed();
    } else if (BigNumber.isBigNumber(a)) {
      return a.toFixed();
    } else if (a._tname !== undefined) {
      return a._tname;
    } else {
      return a.toString();
    }
  }
  $module.escapeCharacter = function(cp) {
    let s = String.fromCodePoint(cp.value)
    switch (s) {
      case '\n': return "\\n";
      case '\r': return "\\r";
      case '\t': return "\\t";
      case '\0': return "\\0";
      case '\'': return "\\'";
      case '\"': return "\\\"";
      case '\\': return "\\\\";
      default: return s;
    };
  }
  $module.NewObject = function() {
    return { _tname: "object" };
  }
  $module.InstanceOfTrait = function(obj, trait) {
    return obj._parentTraits !== undefined && obj._parentTraits().includes(trait);
  }
  $module.Rtd_bool = class {
    static get Default() { return false; }
  }
  $module.Rtd_char = class {
    static get Default() { return 'D'; }  // See CharType.DefaultValue in Dafny source code
  }
  $module.Rtd_codepoint = class {
    static get Default() { return new _dafny.CodePoint('D'.codePointAt(0)); }
  }
  $module.Rtd_int = class {
    static get Default() { return BigNumber(0); }
  }
  $module.Rtd_number = class {
    static get Default() { return 0; }
  }
  $module.Rtd_ref = class {
    static get Default() { return null; }
  }
  $module.Rtd_array = class {
    static get Default() { return []; }
  }
  $module.ZERO = new BigNumber(0);
  $module.ONE = new BigNumber(1);
  $module.NUMBER_LIMIT = new BigNumber(0x20).multipliedBy(0x1000000000000);  // 2^53
  $module.Tuple = class Tuple extends Array {
    constructor(...elems) {
      super(...elems);
    }
    toString() {
      return "(" + arrayElementsToString(this) + ")";
    }
    equals(other) {
      if (this === other) {
        return true;
      }
      for (let i = 0; i < this.length; i++) {
        if (!_dafny.areEqual(this[i], other[i])) {
          return false;
        }
      }
      return true;
    }
    static Default(...values) {
      return Tuple.of(...values);
    }
    static Rtd(...rtdArgs) {
      return {
        Default: Tuple.from(rtdArgs, rtd => rtd.Default)
      };
    }
  }
  $module.Set = class Set extends Array {
    constructor() {
      super();
    }
    static get Default() {
      return Set.Empty;
    }
    toString() {
      return "{" + arrayElementsToString(this) + "}";
    }
    static get Empty() {
      if (this._empty === undefined) {
        this._empty = new Set();
      }
      return this._empty;
    }
    static fromElements(...elmts) {
      let s = new Set();
      for (let k of elmts) {
        s.add(k);
      }
      return s;
    }
    contains(k) {
      for (let i = 0; i < this.length; i++) {
        if (_dafny.areEqual(this[i], k)) {
          return true;
        }
      }
      return false;
    }
    add(k) {  // mutates the Set; use only during construction
      if (!this.contains(k)) {
        this.push(k);
      }
    }
    equals(other) {
      if (this === other) {
        return true;
      } else if (this.length !== other.length) {
        return false;
      }
      for (let e of this) {
        if (!other.contains(e)) {
          return false;
        }
      }
      return true;
    }
    get Elements() {
      return this;
    }
    Union(that) {
      if (this.length === 0) {
        return that;
      } else if (that.length === 0) {
        return this;
      } else {
        let s = Set.of(...this);
        for (let k of that) {
          s.add(k);
        }
        return s;
      }
    }
    Intersect(that) {
      if (this.length === 0) {
        return this;
      } else if (that.length === 0) {
        return that;
      } else {
        let s = new Set();
        for (let k of this) {
          if (that.contains(k)) {
            s.push(k);
          }
        }
        return s;
      }
    }
    Difference(that) {
      if (this.length == 0 || that.length == 0) {
        return this;
      } else {
        let s = new Set();
        for (let k of this) {
          if (!that.contains(k)) {
            s.push(k);
          }
        }
        return s;
      }
    }
    IsDisjointFrom(that) {
      for (let k of this) {
        if (that.contains(k)) {
          return false;
        }
      }
      return true;
    }
    IsSubsetOf(that) {
      if (that.length < this.length) {
        return false;
      }
      for (let k of this) {
        if (!that.contains(k)) {
          return false;
        }
      }
      return true;
    }
    IsProperSubsetOf(that) {
      if (that.length <= this.length) {
        return false;
      }
      for (let k of this) {
        if (!that.contains(k)) {
          return false;
        }
      }
      return true;
    }
    get AllSubsets() {
      return this.AllSubsets_();
    }
    *AllSubsets_() {
      // Start by putting all set elements into a list, but don't include null
      let elmts = Array.of(...this);
      let n = elmts.length;
      let which = new Array(n);
      which.fill(false);
      let a = [];
      while (true) {
        yield Set.of(...a);
        // "add 1" to "which", as if doing a carry chain.  For every digit changed, change the membership of the corresponding element in "a".
        let i = 0;
        for (; i < n && which[i]; i++) {
          which[i] = false;
          // remove elmts[i] from a
          for (let j = 0; j < a.length; j++) {
            if (_dafny.areEqual(a[j], elmts[i])) {
              // move the last element of a into slot j
              a[j] = a[-1];
              a.pop();
              break;
            }
          }
        }
        if (i === n) {
          // we have cycled through all the subsets
          break;
        }
        which[i] = true;
        a.push(elmts[i]);
      }
    }
  }
  $module.MultiSet = class MultiSet extends Array {
    constructor() {
      super();
    }
    static get Default() {
      return MultiSet.Empty;
    }
    toString() {
      let s = "multiset{";
      let sep = "";
      for (let e of this) {
        let [k, n] = e;
        let ks = _dafny.toString(k);
        while (!n.isZero()) {
          n = n.minus(1);
          s += sep + ks;
          sep = ", ";
        }
      }
      s += "}";
      return s;
    }
    static get Empty() {
      if (this._empty === undefined) {
        this._empty = new MultiSet();
      }
      return this._empty;
    }
    static fromElements(...elmts) {
      let s = new MultiSet();
      for (let e of elmts) {
        s.add(e, _dafny.ONE);
      }
      return s;
    }
    static FromArray(arr) {
      let s = new MultiSet();
      for (let e of arr) {
        s.add(e, _dafny.ONE);
      }
      return s;
    }
    cardinality() {
      let c = _dafny.ZERO;
      for (let e of this) {
        let [k, n] = e;
        c = c.plus(n);
      }
      return c;
    }
    clone() {
      let s = new MultiSet();
      for (let e of this) {
        let [k, n] = e;
        s.push([k, n]);  // make sure to create a new array [k, n] here
      }
      return s;
    }
    findIndex(k) {
      for (let i = 0; i < this.length; i++) {
        if (_dafny.areEqual(this[i][0], k)) {
          return i;
        }
      }
      return this.length;
    }
    get(k) {
      let i = this.findIndex(k);
      if (i === this.length) {
        return _dafny.ZERO;
      } else {
        return this[i][1];
      }
    }
    contains(k) {
      return !this.get(k).isZero();
    }
    add(k, n) {
      let i = this.findIndex(k);
      if (i === this.length) {
        this.push([k, n]);
      } else {
        let m = this[i][1];
        this[i] = [k, m.plus(n)];
      }
    }
    update(k, n) {
      let i = this.findIndex(k);
      if (i < this.length && this[i][1].isEqualTo(n)) {
        return this;
      } else if (i === this.length && n.isZero()) {
        return this;
      } else if (i === this.length) {
        let m = this.slice();
        m.push([k, n]);
        return m;
      } else {
        let m = this.slice();
        m[i] = [k, n];
        return m;
      }
    }
    equals(other) {
      if (this === other) {
        return true;
      }
      for (let e of this) {
        let [k, n] = e;
        let m = other.get(k);
        if (!n.isEqualTo(m)) {
          return false;
        }
      }
      return this.cardinality().isEqualTo(other.cardinality());
    }
    get Elements() {
      return this.Elements_();
    }
    *Elements_() {
      for (let i = 0; i < this.length; i++) {
        let [k, n] = this[i];
        while (!n.isZero()) {
          yield k;
          n = n.minus(1);
        }
      }
    }
    get UniqueElements() {
      return this.UniqueElements_();
    }
    *UniqueElements_() {
      for (let e of this) {
        let [k, n] = e;
        if (!n.isZero()) {
          yield k;
        }
      }
    }
    Union(that) {
      if (this.length === 0) {
        return that;
      } else if (that.length === 0) {
        return this;
      } else {
        let s = this.clone();
        for (let e of that) {
          let [k, n] = e;
          s.add(k, n);
        }
        return s;
      }
    }
    Intersect(that) {
      if (this.length === 0) {
        return this;
      } else if (that.length === 0) {
        return that;
      } else {
        let s = new MultiSet();
        for (let e of this) {
          let [k, n] = e;
          let m = that.get(k);
          if (!m.isZero()) {
            s.push([k, m.isLessThan(n) ? m : n]);
          }
        }
        return s;
      }
    }
    Difference(that) {
      if (this.length === 0 || that.length === 0) {
        return this;
      } else {
        let s = new MultiSet();
        for (let e of this) {
          let [k, n] = e;
          let d = n.minus(that.get(k));
          if (d.isGreaterThan(0)) {
            s.push([k, d]);
          }
        }
        return s;
      }
    }
    IsDisjointFrom(that) {
      let intersection = this.Intersect(that);
      return intersection.cardinality().isZero();
    }
    IsSubsetOf(that) {
      for (let e of this) {
        let [k, n] = e;
        let m = that.get(k);
        if (!n.isLessThanOrEqualTo(m)) {
          return false;
        }
      }
      return true;
    }
    IsProperSubsetOf(that) {
      return this.IsSubsetOf(that) && this.cardinality().isLessThan(that.cardinality());
    }
  }
  $module.CodePoint = class CodePoint {
    constructor(value) {
      this.value = value
    }
    equals(other) {
      if (this === other) {
        return true;
      }
      return this.value === other.value
    }
    isLessThan(other) {
      return this.value < other.value
    }
    isLessThanOrEqual(other) {
      return this.value <= other.value
    }
    toString() {
      return "'" + $module.escapeCharacter(this) + "'";
    }
    static isCodePoint(i) {
      return (
        (_dafny.ZERO.isLessThanOrEqualTo(i) && i.isLessThan(new BigNumber(0xD800))) ||
        (new BigNumber(0xE000).isLessThanOrEqualTo(i) && i.isLessThan(new BigNumber(0x11_0000))))
    }
  }
  $module.Seq = class Seq extends Array {
    constructor(...elems) {
      super(...elems);
    }
    static get Default() {
      return Seq.of();
    }
    static Create(n, init) {
      return Seq.from({length: n}, (_, i) => init(new BigNumber(i)));
    }
    static UnicodeFromString(s) {
      return new Seq(...([...s].map(c => new _dafny.CodePoint(c.codePointAt(0)))))
    }
    toString() {
      return "[" + arrayElementsToString(this) + "]";
    }
    toVerbatimString(asLiteral) {
      if (asLiteral) {
        return '"' + this.map(c => _dafny.escapeCharacter(c)).join("") + '"';
      } else {
        return this.map(c => String.fromCodePoint(c.value)).join("");
      }
    }
    static update(s, i, v) {
      if (typeof s === "string") {
        let p = s.slice(0, i);
        let q = s.slice(i.toNumber() + 1);
        return p.concat(v, q);
      } else {
        let t = s.slice();
        t[i] = v;
        return t;
      }
    }
    equals(other) {
      if (this === other) {
        return true;
      } else if (this.length !== other.length) {
        return false;
      }
      for (let i = 0; i < this.length; i++) {
        if (!_dafny.areEqual(this[i], other[i])) {
          return false;
        }
      }
      return true;
    }
    static contains(s, k) {
      if (typeof s === "string") {
        return s.includes(k);
      } else {
        for (let x of s) {
          if (_dafny.areEqual(x, k)) {
            return true;
          }
        }
        return false;
      }
    }
    get Elements() {
      return this;
    }
    get UniqueElements() {
      return _dafny.Set.fromElements(...this);
    }
    static Concat(a, b) {
      if (typeof a === "string" || typeof b === "string") {
        // string concatenation, so make sure both operands are strings before concatenating
        if (typeof a !== "string") {
          // a must be a Seq
          a = a.join("");
        }
        if (typeof b !== "string") {
          // b must be a Seq
          b = b.join("");
        }
        return a + b;
      } else {
        // ordinary concatenation
        let r = Seq.of(...a);
        r.push(...b);
        return r;
      }
    }
    static JoinIfPossible(x) {
      try { return x.join(""); } catch(_error) { return x; }
    }
    static IsPrefixOf(a, b) {
      if (b.length < a.length) {
        return false;
      }
      for (let i = 0; i < a.length; i++) {
        if (!_dafny.areEqual(a[i], b[i])) {
          return false;
        }
      }
      return true;
    }
    static IsProperPrefixOf(a, b) {
      if (b.length <= a.length) {
        return false;
      }
      for (let i = 0; i < a.length; i++) {
        if (!_dafny.areEqual(a[i], b[i])) {
          return false;
        }
      }
      return true;
    }
  }
  $module.Map = class Map extends Array {
    constructor() {
      super();
    }
    static get Default() {
      return Map.of();
    }
    toString() {
      return "map[" + this.map(maplet => _dafny.toString(maplet[0]) + " := " + _dafny.toString(maplet[1])).join(", ") + "]";
    }
    static get Empty() {
      if (this._empty === undefined) {
        this._empty = new Map();
      }
      return this._empty;
    }
    findIndex(k) {
      for (let i = 0; i < this.length; i++) {
        if (_dafny.areEqual(this[i][0], k)) {
          return i;
        }
      }
      return this.length;
    }
    get(k) {
      let i = this.findIndex(k);
      if (i === this.length) {
        return undefined;
      } else {
        return this[i][1];
      }
    }
    contains(k) {
      return this.findIndex(k) < this.length;
    }
    update(k, v) {
      let m = this.slice();
      m.updateUnsafe(k, v);
      return m;
    }
    // Similar to update, but make the modification in-place.
    // Meant to be used in the map constructor.
    updateUnsafe(k, v) {
      let m = this;
      let i = m.findIndex(k);
      m[i] = [k, v];
      return m;
    }
    equals(other) {
      if (this === other) {
        return true;
      } else if (this.length !== other.length) {
        return false;
      }
      for (let e of this) {
        let [k, v] = e;
        let w = other.get(k);
        if (w === undefined || !_dafny.areEqual(v, w)) {
          return false;
        }
      }
      return true;
    }
    get Keys() {
      let s = new _dafny.Set();
      for (let e of this) {
        let [k, v] = e;
        s.push(k);
      }
      return s;
    }
    get Values() {
      let s = new _dafny.Set();
      for (let e of this) {
        let [k, v] = e;
        s.add(v);
      }
      return s;
    }
    get Items() {
      let s = new _dafny.Set();
      for (let e of this) {
        let [k, v] = e;
        s.push(_dafny.Tuple.of(k, v));
      }
      return s;
    }
    Merge(that) {
      let m = that.slice();
      for (let e of this) {
        let [k, v] = e;
        let i = m.findIndex(k);
        if (i == m.length) {
          m[i] = [k, v];
        }
      }
      return m;
    }
    Subtract(keys) {
      if (this.length === 0 || keys.length === 0) {
        return this;
      }
      let m = new Map();
      for (let e of this) {
        let [k, v] = e;
        if (!keys.contains(k)) {
          m[m.length] = e;
        }
      }
      return m;
    }
  }
  $module.newArray = function(initValue, ...dims) {
    return { dims: dims, elmts: buildArray(initValue, ...dims) };
  }
  $module.BigOrdinal = class BigOrdinal {
    static get Default() {
      return _dafny.ZERO;
    }
    static IsLimit(ord) {
      return ord.isZero();
    }
    static IsSucc(ord) {
      return ord.isGreaterThan(0);
    }
    static Offset(ord) {
      return ord;
    }
    static IsNat(ord) {
      return true;  // at run time, every ORDINAL is a natural number
    }
  }
  $module.BigRational = class BigRational {
    static get ZERO() {
      if (this._zero === undefined) {
        this._zero = new BigRational(_dafny.ZERO);
      }
      return this._zero;
    }
    constructor (n, d) {
      // requires d === undefined || 1 <= d
      this.num = n;
      this.den = d === undefined ? _dafny.ONE : d;
      // invariant 1 <= den || (num == 0 && den == 0)
    }
    static get Default() {
      return _dafny.BigRational.ZERO;
    }
    // We need to deal with the special case `num == 0 && den == 0`, because
    // that's what C#'s default struct constructor will produce for BigRational. :(
    // To deal with it, we ignore `den` when `num` is 0.
    toString() {
      if (this.num.isZero() || this.den.isEqualTo(1)) {
        return this.num.toFixed() + ".0";
      }
      let answer = this.dividesAPowerOf10(this.den);
      if (answer !== undefined) {
        let n = this.num.multipliedBy(answer[0]);
        let log10 = answer[1];
        let sign, digits;
        if (this.num.isLessThan(0)) {
          sign = "-"; digits = n.negated().toFixed();
        } else {
          sign = ""; digits = n.toFixed();
        }
        if (log10 < digits.length) {
          let digitCount = digits.length - log10;
          return sign + digits.slice(0, digitCount) + "." + digits.slice(digitCount);
        } else {
          return sign + "0." + "0".repeat(log10 - digits.length) + digits;
        }
      } else {
        return "(" + this.num.toFixed() + ".0 / " + this.den.toFixed() + ".0)";
      }
    }
    isPowerOf10(x) {
      if (x.isZero()) {
        return undefined;
      }
      let log10 = 0;
      while (true) {  // invariant: x != 0 && x * 10^log10 == old(x)
        if (x.isEqualTo(1)) {
          return log10;
        } else if (x.mod(10).isZero()) {
          log10++;
          x = x.dividedToIntegerBy(10);
        } else {
          return undefined;
        }
      }
    }
    dividesAPowerOf10(i) {
      let factor = _dafny.ONE;
      let log10 = 0;
      if (i.isLessThanOrEqualTo(_dafny.ZERO)) {
        return undefined;
      }

      // invariant: 1 <= i && i * 10^log10 == factor * old(i)
      while (i.mod(10).isZero()) {
        i = i.dividedToIntegerBy(10);
       log10++;
      }

      while (i.mod(5).isZero()) {
        i = i.dividedToIntegerBy(5);
        factor = factor.multipliedBy(2);
        log10++;
      }
      while (i.mod(2).isZero()) {
        i = i.dividedToIntegerBy(2);
        factor = factor.multipliedBy(5);
        log10++;
      }

      if (i.isEqualTo(_dafny.ONE)) {
        return [factor, log10];
      } else {
        return undefined;
      }
    }
    toBigNumber() {
      if (this.num.isZero() || this.den.isEqualTo(1)) {
        return this.num;
      } else if (this.num.isGreaterThan(0)) {
        return this.num.dividedToIntegerBy(this.den);
      } else {
        return this.num.minus(this.den).plus(1).dividedToIntegerBy(this.den);
      }
    }
    isInteger() {
      return this.equals(new _dafny.BigRational(this.toBigNumber(), _dafny.ONE));
    }
    // Returns values such that aa/dd == a and bb/dd == b.
    normalize(b) {
      let a = this;
      let aa, bb, dd;
      if (a.num.isZero()) {
        aa = a.num;
        bb = b.num;
        dd = b.den;
      } else if (b.num.isZero()) {
        aa = a.num;
        dd = a.den;
        bb = b.num;
      } else {
        let gcd = BigNumberGcd(a.den, b.den);
        let xx = a.den.dividedToIntegerBy(gcd);
        let yy = b.den.dividedToIntegerBy(gcd);
        // We now have a == a.num / (xx * gcd) and b == b.num / (yy * gcd).
        aa = a.num.multipliedBy(yy);
        bb = b.num.multipliedBy(xx);
        dd = a.den.multipliedBy(yy);
      }
      return [aa, bb, dd];
    }
    compareTo(that) {
      // simple things first
      let asign = this.num.isZero() ? 0 : this.num.isLessThan(0) ? -1 : 1;
      let bsign = that.num.isZero() ? 0 : that.num.isLessThan(0) ? -1 : 1;
      if (asign < 0 && 0 <= bsign) {
        return -1;
      } else if (asign <= 0 && 0 < bsign) {
        return -1;
      } else if (bsign < 0 && 0 <= asign) {
        return 1;
      } else if (bsign <= 0 && 0 < asign) {
        return 1;
      }
      let [aa, bb, dd] = this.normalize(that);
      if (aa.isLessThan(bb)) {
        return -1;
      } else if (aa.isEqualTo(bb)){
        return 0;
      } else {
        return 1;
      }
    }
    equals(that) {
      return this.compareTo(that) === 0;
    }
    isLessThan(that) {
      return this.compareTo(that) < 0;
    }
    isAtMost(that) {
      return this.compareTo(that) <= 0;
    }
    plus(b) {
      let [aa, bb, dd] = this.normalize(b);
      return new BigRational(aa.plus(bb), dd);
    }
    minus(b) {
      let [aa, bb, dd] = this.normalize(b);
      return new BigRational(aa.minus(bb), dd);
    }
    negated() {
      return new BigRational(this.num.negated(), this.den);
    }
    multipliedBy(b) {
      return new BigRational(this.num.multipliedBy(b.num), this.den.multipliedBy(b.den));
    }
    dividedBy(b) {
      let a = this;
      // Compute the reciprocal of b
      let bReciprocal;
      if (b.num.isGreaterThan(0)) {
        bReciprocal = new BigRational(b.den, b.num);
      } else {
        // this is the case b.num < 0
        bReciprocal = new BigRational(b.den.negated(), b.num.negated());
      }
      return a.multipliedBy(bReciprocal);
    }
  }
  $module.EuclideanDivisionNumber = function(a, b) {
    if (0 <= a) {
      if (0 <= b) {
        // +a +b: a/b
        return Math.floor(a / b);
      } else {
        // +a -b: -(a/(-b))
        return -Math.floor(a / -b);
      }
    } else {
      if (0 <= b) {
        // -a +b: -((-a-1)/b) - 1
        return -Math.floor((-a-1) / b) - 1;
      } else {
        // -a -b: ((-a-1)/(-b)) + 1
        return Math.floor((-a-1) / -b) + 1;
      }
    }
  }
  $module.EuclideanDivision = function(a, b) {
    if (a.isGreaterThanOrEqualTo(0)) {
      if (b.isGreaterThanOrEqualTo(0)) {
        // +a +b: a/b
        return a.dividedToIntegerBy(b);
      } else {
        // +a -b: -(a/(-b))
        return a.dividedToIntegerBy(b.negated()).negated();
      }
    } else {
      if (b.isGreaterThanOrEqualTo(0)) {
        // -a +b: -((-a-1)/b) - 1
        return a.negated().minus(1).dividedToIntegerBy(b).negated().minus(1);
      } else {
        // -a -b: ((-a-1)/(-b)) + 1
        return a.negated().minus(1).dividedToIntegerBy(b.negated()).plus(1);
      }
    }
  }
  $module.EuclideanModuloNumber = function(a, b) {
    let bp = Math.abs(b);
    if (0 <= a) {
      // +a: a % bp
      return a % bp;
    } else {
      // c = ((-a) % bp)
      // -a: bp - c if c > 0
      // -a: 0 if c == 0
      let c = (-a) % bp;
      return c === 0 ? c : bp - c;
    }
  }
  $module.ShiftLeft = function(b, n) {
    return b.multipliedBy(new BigNumber(2).exponentiatedBy(n));
  }
  $module.ShiftRight = function(b, n) {
    return b.dividedToIntegerBy(new BigNumber(2).exponentiatedBy(n));
  }
  $module.RotateLeft = function(b, n, w) {  // truncate(b << n) | (b >> (w - n))
    let x = _dafny.ShiftLeft(b, n).mod(new BigNumber(2).exponentiatedBy(w));
    let y = _dafny.ShiftRight(b, w - n);
    return x.plus(y);
  }
  $module.RotateRight = function(b, n, w) {  // (b >> n) | truncate(b << (w - n))
    let x = _dafny.ShiftRight(b, n);
    let y = _dafny.ShiftLeft(b, w - n).mod(new BigNumber(2).exponentiatedBy(w));;
    return x.plus(y);
  }
  $module.BitwiseAnd = function(a, b) {
    let r = _dafny.ZERO;
    const m = _dafny.NUMBER_LIMIT;  // 2^53
    let h = _dafny.ONE;
    while (!a.isZero() && !b.isZero()) {
      let a0 = a.mod(m);
      let b0 = b.mod(m);
      r = r.plus(h.multipliedBy(a0 & b0));
      a = a.dividedToIntegerBy(m);
      b = b.dividedToIntegerBy(m);
      h = h.multipliedBy(m);
    }
    return r;
  }
  $module.BitwiseOr = function(a, b) {
    let r = _dafny.ZERO;
    const m = _dafny.NUMBER_LIMIT;  // 2^53
    let h = _dafny.ONE;
    while (!a.isZero() && !b.isZero()) {
      let a0 = a.mod(m);
      let b0 = b.mod(m);
      r = r.plus(h.multipliedBy(a0 | b0));
      a = a.dividedToIntegerBy(m);
      b = b.dividedToIntegerBy(m);
      h = h.multipliedBy(m);
    }
    r = r.plus(h.multipliedBy(a | b));
    return r;
  }
  $module.BitwiseXor = function(a, b) {
    let r = _dafny.ZERO;
    const m = _dafny.NUMBER_LIMIT;  // 2^53
    let h = _dafny.ONE;
    while (!a.isZero() && !b.isZero()) {
      let a0 = a.mod(m);
      let b0 = b.mod(m);
      r = r.plus(h.multipliedBy(a0 ^ b0));
      a = a.dividedToIntegerBy(m);
      b = b.dividedToIntegerBy(m);
      h = h.multipliedBy(m);
    }
    r = r.plus(h.multipliedBy(a | b));
    return r;
  }
  $module.BitwiseNot = function(a, bits) {
    let r = _dafny.ZERO;
    let h = _dafny.ONE;
    for (let i = 0; i < bits; i++) {
      let bit = a.mod(2);
      if (bit.isZero()) {
        r = r.plus(h);
      }
      a = a.dividedToIntegerBy(2);
      h = h.multipliedBy(2);
    }
    return r;
  }
  $module.Quantifier = function(vals, frall, pred) {
    for (let u of vals) {
      if (pred(u) !== frall) { return !frall; }
    }
    return frall;
  }
  $module.PlusChar = function(a, b) {
    return String.fromCharCode(a.charCodeAt(0) + b.charCodeAt(0));
  }
  $module.UnicodePlusChar = function(a, b) {
    return new _dafny.CodePoint(a.value + b.value);
  }
  $module.MinusChar = function(a, b) {
    return String.fromCharCode(a.charCodeAt(0) - b.charCodeAt(0));
  }
  $module.UnicodeMinusChar = function(a, b) {
    return new _dafny.CodePoint(a.value - b.value);
  }
  $module.AllBooleans = function*() {
    yield false;
    yield true;
  }
  $module.AllChars = function*() {
    for (let i = 0; i < 0x10000; i++) {
      yield String.fromCharCode(i);
    }
  }
  $module.AllUnicodeChars = function*() {
    for (let i = 0; i < 0xD800; i++) {
      yield new _dafny.CodePoint(i);
    }
    for (let i = 0xE0000; i < 0x110000; i++) {
      yield new _dafny.CodePoint(i);
    }
  }
  $module.AllIntegers = function*() {
    yield _dafny.ZERO;
    for (let j = _dafny.ONE;; j = j.plus(1)) {
      yield j;
      yield j.negated();
    }
  }
  $module.IntegerRange = function*(lo, hi) {
    if (lo === null) {
      while (true) {
        hi = hi.minus(1);
        yield hi;
      }
    } else if (hi === null) {
      while (true) {
        yield lo;
        lo = lo.plus(1);
      }
    } else {
      while (lo.isLessThan(hi)) {
        yield lo;
        lo = lo.plus(1);
      }
    }
  }
  $module.SingleValue = function*(v) {
    yield v;
  }
  $module.HaltException = class HaltException extends Error {
    constructor(message) {
      super(message)
    }
  }
  $module.HandleHaltExceptions = function(f) {
    try {
      f()
    } catch (e) {
      if (e instanceof _dafny.HaltException) {
        process.stdout.write("[Program halted] " + e.message + "\n")
        process.exitCode = 1
      } else {
        throw e
      }
    }
  }
  $module.FromMainArguments = function(args) {
    var a = [...args];
    a.splice(0, 2, args[0] + " " + args[1]);
    return a;
  }
  $module.UnicodeFromMainArguments = function(args) {
    return $module.FromMainArguments(args).map(_dafny.Seq.UnicodeFromString);
  }
  return $module;

  // What follows are routines private to the Dafny runtime
  function buildArray(initValue, ...dims) {
    if (dims.length === 0) {
      return initValue;
    } else {
      let a = Array(dims[0].toNumber());
      let b = Array.from(a, (x) => buildArray(initValue, ...dims.slice(1)));
      return b;
    }
  }
  function arrayElementsToString(a) {
    // like `a.join(", ")`, but calling _dafny.toString(x) on every element x instead of x.toString()
    let s = "";
    let sep = "";
    for (let x of a) {
      s += sep + _dafny.toString(x);
      sep = ", ";
    }
    return s;
  }
  function BigNumberGcd(a, b){  // gcd of two non-negative BigNumber's
    while (true) {
      if (a.isZero()) {
        return b;
      } else if (b.isZero()) {
        return a;
      }
      if (a.isLessThan(b)) {
        b = b.modulo(a);
      } else {
        a = a.modulo(b);
      }
    }
  }
})();
// Dafny program systemModulePopulator.dfy compiled into JavaScript
let _System = (function() {
  let $module = {};

  $module.nat = class nat {
    constructor () {
    }
    static get Default() {
      return _dafny.ZERO;
    }
    static _Is(__source) {
      let _0_x = (__source);
      return (_dafny.ZERO).isLessThanOrEqualTo(_0_x);
    }
  };

  return $module;
})(); // end of module _System
let Ls20Level2 = (function() {
  let $module = {};

  $module.__default = class __default {
    constructor () {
      this._tname = "Ls20Level2._default";
    }
    _parentTraits() {
      return [];
    }
    static IsWall(x, y) {
      return ((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(_dafny.ZERO))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(_dafny.ONE)))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(2))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(3))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(4))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(5))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(7))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(8))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(_dafny.ZERO)) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(_dafny.ONE)))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(new BigNumber(5))))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(new BigNumber(7))))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(new BigNumber(8))))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(_dafny.ONE)) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(2))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(2))) && ((y).isEqualTo(_dafny.ONE)))) || (((x).isEqualTo(new BigNumber(2))) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(new BigNumber(2))) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(new BigNumber(2))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(new BigNumber(5))))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(new BigNumber(7))))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(new BigNumber(8))))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(new BigNumber(3))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(3))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(4))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(5))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(7))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(8))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(new BigNumber(4))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(5))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(5))) && ((y).isEqualTo(new BigNumber(5))))) || (((x).isEqualTo(new BigNumber(5))) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(new BigNumber(5))) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(new BigNumber(5))) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(new BigNumber(5))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(6))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(6))) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(new BigNumber(6))) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(new BigNumber(6))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(new BigNumber(3))))) || (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(new BigNumber(4))))) || (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(new BigNumber(7))))) || (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(new BigNumber(8))))) || (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(8))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(8))) && ((y).isEqualTo(new BigNumber(4))))) || (((x).isEqualTo(new BigNumber(8))) && ((y).isEqualTo(new BigNumber(5))))) || (((x).isEqualTo(new BigNumber(8))) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(new BigNumber(8))) && ((y).isEqualTo(new BigNumber(7))))) || (((x).isEqualTo(new BigNumber(8))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(9))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(9))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(10))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(10))) && ((y).isEqualTo(_dafny.ONE)))) || (((x).isEqualTo(new BigNumber(10))) && ((y).isEqualTo(new BigNumber(2))))) || (((x).isEqualTo(new BigNumber(10))) && ((y).isEqualTo(new BigNumber(3))))) || (((x).isEqualTo(new BigNumber(10))) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(new BigNumber(10))) && ((y).isEqualTo(new BigNumber(11))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(_dafny.ZERO)))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(_dafny.ONE)))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(2))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(3))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(4))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(5))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(6))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(7))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(8))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(9))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(10))))) || (((x).isEqualTo(new BigNumber(11))) && ((y).isEqualTo(new BigNumber(11))));
    };
    static EnergyIndex(x, y) {
      if (((x).isEqualTo(new BigNumber(2))) && ((y).isEqualTo(new BigNumber(3)))) {
        return _dafny.ZERO;
      } else if (((x).isEqualTo(new BigNumber(7))) && ((y).isEqualTo(new BigNumber(10)))) {
        return _dafny.ONE;
      } else {
        return new BigNumber(-1);
      }
    };
    static EatenLegal(m) {
      return ((((m).isEqualTo(_dafny.ZERO)) || ((m).isEqualTo(_dafny.ONE))) || ((m).isEqualTo(new BigNumber(2)))) || ((m).isEqualTo(new BigNumber(3)));
    };
    static AddBit(m, i) {
      if ((i).isEqualTo(_dafny.ZERO)) {
        return (m).plus(_dafny.ONE);
      } else if ((i).isEqualTo(_dafny.ONE)) {
        return (m).plus(new BigNumber(2));
      } else {
        return m;
      }
    };
    static HasBit(m, i) {
      if ((i).isEqualTo(_dafny.ZERO)) {
        return ((_dafny.EuclideanDivision(m, _dafny.ONE)).mod(new BigNumber(2))).isEqualTo(_dafny.ONE);
      } else if ((i).isEqualTo(_dafny.ONE)) {
        return ((_dafny.EuclideanDivision(m, new BigNumber(2))).mod(new BigNumber(2))).isEqualTo(_dafny.ONE);
      } else {
        return false;
      }
    };
    static Legal(s) {
      return ((((((((_dafny.ZERO).isLessThanOrEqualTo((s).dtor_x)) && (((s).dtor_x).isLessThan(Ls20Level2.__default.W))) && (((_dafny.ZERO).isLessThanOrEqualTo((s).dtor_y)) && (((s).dtor_y).isLessThan(Ls20Level2.__default.H)))) && (!(Ls20Level2.__default.IsWall((s).dtor_x, (s).dtor_y)))) && (((_dafny.ZERO).isLessThanOrEqualTo((s).dtor_rot)) && (((s).dtor_rot).isLessThan(new BigNumber(4))))) && (((_dafny.ONE).isLessThanOrEqualTo((s).dtor_lives)) && (((s).dtor_lives).isLessThanOrEqualTo(Ls20Level2.__default.LIVES)))) && ((((_dafny.ZERO).minus(Ls20Level2.__default.DEC)).isLessThanOrEqualTo((s).dtor_steps)) && (((s).dtor_steps).isLessThanOrEqualTo(Ls20Level2.__default.STEPS)))) && (Ls20Level2.__default.EatenLegal((s).dtor_eaten));
    };
    static Start() {
      return Ls20Level2.S.create_S(Ls20Level2.__default.START__X, Ls20Level2.__default.START__Y, Ls20Level2.__default.START__ROT, Ls20Level2.__default.LIVES, Ls20Level2.__default.STEPS, _dafny.ZERO, Ls20Level2.Status.create_Play());
    };
    static Delta(a) {
      if ((a).isEqualTo(_dafny.ONE)) {
        return _dafny.Tuple.of(_dafny.ZERO, new BigNumber(-1));
      } else if ((a).isEqualTo(new BigNumber(2))) {
        return _dafny.Tuple.of(_dafny.ZERO, _dafny.ONE);
      } else if ((a).isEqualTo(new BigNumber(3))) {
        return _dafny.Tuple.of(new BigNumber(-1), _dafny.ZERO);
      } else if ((a).isEqualTo(new BigNumber(4))) {
        return _dafny.Tuple.of(_dafny.ONE, _dafny.ZERO);
      } else {
        return _dafny.Tuple.of(_dafny.ZERO, _dafny.ZERO);
      }
    };
    static Matches(rot) {
      return (rot).isEqualTo(Ls20Level2.__default.GOAL__ROT);
    };
    static Step(s, a) {
      if (((!_dafny.areEqual((s).dtor_status, Ls20Level2.Status.create_Play())) || ((a).isLessThan(_dafny.ONE))) || ((new BigNumber(4)).isLessThan(a))) {
        return s;
      } else {
        let _0_d = Ls20Level2.__default.Delta(a);
        let _1_tx = ((s).dtor_x).plus((_0_d)[0]);
        let _2_ty = ((s).dtor_y).plus((_0_d)[1]);
        let _3_isWall = Ls20Level2.__default.IsWall(_1_tx, _2_ty);
        let _4_isGoal = ((_1_tx).isEqualTo(Ls20Level2.__default.GOAL__X)) && ((_2_ty).isEqualTo(Ls20Level2.__default.GOAL__Y));
        let _5_isRot = ((_1_tx).isEqualTo(Ls20Level2.__default.ROT__TILE__X)) && ((_2_ty).isEqualTo(Ls20Level2.__default.ROT__TILE__Y));
        let _6_ei = Ls20Level2.__default.EnergyIndex(_1_tx, _2_ty);
        let _7_gotEnergy = (((!(_3_isWall)) && ((_dafny.ZERO).isLessThanOrEqualTo(_6_ei))) && ((_6_ei).isLessThan(Ls20Level2.__default.NE))) && (!(Ls20Level2.__default.HasBit((s).dtor_eaten, _6_ei)));
        let _8_rot_k = (((!(_3_isWall)) && (_5_isRot)) ? ((((s).dtor_rot).plus(_dafny.ONE)).mod(new BigNumber(4))) : ((s).dtor_rot));
        let _9_flash = (((!(_3_isWall)) && (_4_isGoal)) && (!(Ls20Level2.__default.Matches((s).dtor_rot)))) || ((((Ls20Level2.__default.TILE__FLASH) && (!(_3_isWall))) && (_5_isRot)) && (Ls20Level2.__default.Matches(_8_rot_k)));
        let _10_blocked = (_3_isWall) || ((_4_isGoal) && (!(Ls20Level2.__default.Matches((s).dtor_rot))));
        let _11_x_k = ((_10_blocked) ? ((s).dtor_x) : (_1_tx));
        let _12_y_k = ((_10_blocked) ? ((s).dtor_y) : (_2_ty));
        let _13_eaten_k = ((_7_gotEnergy) ? (Ls20Level2.__default.AddBit((s).dtor_eaten, _6_ei)) : ((s).dtor_eaten));
        if (_9_flash) {
          return Ls20Level2.S.create_S(_11_x_k, _12_y_k, _8_rot_k, (s).dtor_lives, (s).dtor_steps, _13_eaten_k, Ls20Level2.Status.create_Play());
        } else if (_7_gotEnergy) {
          return Ls20Level2.S.create_S(_11_x_k, _12_y_k, _8_rot_k, (s).dtor_lives, Ls20Level2.__default.STEPS, _13_eaten_k, Ls20Level2.Status.create_Play());
        } else {
          let _14_steps_k = (((_dafny.ZERO).isLessThanOrEqualTo((s).dtor_steps)) ? (((s).dtor_steps).minus(Ls20Level2.__default.DEC)) : ((s).dtor_steps));
          let _15_ranOut = (_14_steps_k).isLessThan(_dafny.ZERO);
          let _16_won = (((_11_x_k).isEqualTo(Ls20Level2.__default.GOAL__X)) && ((_12_y_k).isEqualTo(Ls20Level2.__default.GOAL__Y))) && (Ls20Level2.__default.Matches(_8_rot_k));
          if (_16_won) {
            return Ls20Level2.S.create_S(_11_x_k, _12_y_k, _8_rot_k, (s).dtor_lives, _14_steps_k, _13_eaten_k, Ls20Level2.Status.create_Win());
          } else if (_15_ranOut) {
            if ((((s).dtor_lives).minus(_dafny.ONE)).isEqualTo(_dafny.ZERO)) {
              return Ls20Level2.S.create_S(_11_x_k, _12_y_k, _8_rot_k, _dafny.ZERO, _14_steps_k, _13_eaten_k, Ls20Level2.Status.create_Over());
            } else {
              return Ls20Level2.S.create_S(Ls20Level2.__default.START__X, Ls20Level2.__default.START__Y, Ls20Level2.__default.START__ROT, ((s).dtor_lives).minus(_dafny.ONE), Ls20Level2.__default.STEPS, _dafny.ZERO, Ls20Level2.Status.create_Play());
            }
          } else {
            return Ls20Level2.S.create_S(_11_x_k, _12_y_k, _8_rot_k, (s).dtor_lives, _14_steps_k, _13_eaten_k, Ls20Level2.Status.create_Play());
          }
        }
      }
    };
    static Reset(s) {
      return Ls20Level2.__default.Start();
    };
    static RunFrom(s, path, i) {
      TAIL_CALL_START: while (true) {
        if ((i).isEqualTo(new BigNumber((path).length))) {
          return s;
        } else {
          let _in0 = Ls20Level2.__default.Step(s, (path)[i]);
          let _in1 = path;
          let _in2 = (i).plus(_dafny.ONE);
          s = _in0;
          path = _in1;
          i = _in2;
          continue TAIL_CALL_START;
        }
      }
    };
    static Run(s, path) {
      return Ls20Level2.__default.RunFrom(s, path, _dafny.ZERO);
    };
    static LegalOrOver(s) {
      return (Ls20Level2.__default.Legal(s)) || ((_dafny.areEqual((s).dtor_status, Ls20Level2.Status.create_Over())) && (((s).dtor_lives).isEqualTo(_dafny.ZERO)));
    };
    static Chunk0(s) {
      return Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(s, _dafny.ONE), new BigNumber(4)), _dafny.ONE), _dafny.ONE), _dafny.ONE), _dafny.ONE), _dafny.ONE), new BigNumber(4)), new BigNumber(4)), new BigNumber(2));
    };
    static Chunk1(s) {
      return Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(s, new BigNumber(4)), new BigNumber(2)), new BigNumber(2)), new BigNumber(2)), new BigNumber(2)), new BigNumber(2)), new BigNumber(2)), _dafny.ONE), new BigNumber(2)), new BigNumber(2));
    };
    static Chunk2(s) {
      return Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(s, new BigNumber(3)), new BigNumber(3)), new BigNumber(4)), _dafny.ONE), new BigNumber(4)), _dafny.ONE), _dafny.ONE), _dafny.ONE), _dafny.ONE), _dafny.ONE);
    };
    static Chunk3(s) {
      return Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(s, _dafny.ONE), _dafny.ONE), new BigNumber(3)), new BigNumber(3)), new BigNumber(3)), new BigNumber(3)), new BigNumber(3)), new BigNumber(3)), new BigNumber(2)), new BigNumber(3));
    };
    static Chunk4(s) {
      return Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(Ls20Level2.__default.Step(s, new BigNumber(2)), new BigNumber(2)), new BigNumber(2)), new BigNumber(2)), new BigNumber(2));
    };
    static PlayWitness(s) {
      return Ls20Level2.__default.Chunk4(Ls20Level2.__default.Chunk3(Ls20Level2.__default.Chunk2(Ls20Level2.__default.Chunk1(Ls20Level2.__default.Chunk0(s)))));
    };
    static Apply(x, y, rot, lives, steps, eaten, status, a) {
      return Ls20Level2.__default.Step(Ls20Level2.S.create_S(x, y, rot, lives, steps, eaten, (((status).isEqualTo(_dafny.ZERO)) ? (Ls20Level2.Status.create_Play()) : ((((status).isEqualTo(_dafny.ONE)) ? (Ls20Level2.Status.create_Win()) : (Ls20Level2.Status.create_Over()))))), a);
    };
    static StatusCode(s) {
      let _source0 = (s).dtor_status;
      {
        if (_source0.is_Play) {
          return _dafny.ZERO;
        }
      }
      {
        if (_source0.is_Win) {
          return _dafny.ONE;
        }
      }
      {
        return new BigNumber(2);
      }
    };
    static get NE() {
      return new BigNumber(2);
    };
    static get W() {
      return new BigNumber(12);
    };
    static get H() {
      return new BigNumber(12);
    };
    static get LIVES() {
      return new BigNumber(3);
    };
    static get DEC() {
      return new BigNumber(2);
    };
    static get STEPS() {
      return new BigNumber(42);
    };
    static get START__X() {
      return new BigNumber(5);
    };
    static get START__Y() {
      return new BigNumber(8);
    };
    static get START__ROT() {
      return _dafny.ZERO;
    };
    static get GOAL__ROT() {
      return new BigNumber(3);
    };
    static get GOAL__X() {
      return new BigNumber(2);
    };
    static get GOAL__Y() {
      return new BigNumber(8);
    };
    static get ROT__TILE__X() {
      return new BigNumber(9);
    };
    static get ROT__TILE__Y() {
      return new BigNumber(9);
    };
    static get TILE__FLASH() {
      return false;
    };
    static get WITNESS() {
      return _dafny.Seq.of(_dafny.ONE, new BigNumber(4), _dafny.ONE, _dafny.ONE, _dafny.ONE, _dafny.ONE, _dafny.ONE, new BigNumber(4), new BigNumber(4), new BigNumber(2), new BigNumber(4), new BigNumber(2), new BigNumber(2), new BigNumber(2), new BigNumber(2), new BigNumber(2), new BigNumber(2), _dafny.ONE, new BigNumber(2), new BigNumber(2), new BigNumber(3), new BigNumber(3), new BigNumber(4), _dafny.ONE, new BigNumber(4), _dafny.ONE, _dafny.ONE, _dafny.ONE, _dafny.ONE, _dafny.ONE, _dafny.ONE, _dafny.ONE, new BigNumber(3), new BigNumber(3), new BigNumber(3), new BigNumber(3), new BigNumber(3), new BigNumber(3), new BigNumber(2), new BigNumber(3), new BigNumber(2), new BigNumber(2), new BigNumber(2), new BigNumber(2), new BigNumber(2));
    };
  };

  $module.Status = class Status {
    constructor(tag) {
      this.$tag = tag;
    }
    static create_Play() {
      let $dt = new Status(0);
      return $dt;
    }
    static create_Win() {
      let $dt = new Status(1);
      return $dt;
    }
    static create_Over() {
      let $dt = new Status(2);
      return $dt;
    }
    get is_Play() { return this.$tag === 0; }
    get is_Win() { return this.$tag === 1; }
    get is_Over() { return this.$tag === 2; }
    static get AllSingletonConstructors() {
      return this.AllSingletonConstructors_();
    }
    static *AllSingletonConstructors_() {
      yield Status.create_Play();
      yield Status.create_Win();
      yield Status.create_Over();
    }
    toString() {
      if (this.$tag === 0) {
        return "Ls20Level2.Status.Play";
      } else if (this.$tag === 1) {
        return "Ls20Level2.Status.Win";
      } else if (this.$tag === 2) {
        return "Ls20Level2.Status.Over";
      } else  {
        return "<unexpected>";
      }
    }
    equals(other) {
      if (this === other) {
        return true;
      } else if (this.$tag === 0) {
        return other.$tag === 0;
      } else if (this.$tag === 1) {
        return other.$tag === 1;
      } else if (this.$tag === 2) {
        return other.$tag === 2;
      } else  {
        return false; // unexpected
      }
    }
    static Default() {
      return Ls20Level2.Status.create_Play();
    }
    static Rtd() {
      return class {
        static get Default() {
          return Status.Default();
        }
      };
    }
  }

  $module.S = class S {
    constructor(tag) {
      this.$tag = tag;
    }
    static create_S(x, y, rot, lives, steps, eaten, status) {
      let $dt = new S(0);
      $dt.x = x;
      $dt.y = y;
      $dt.rot = rot;
      $dt.lives = lives;
      $dt.steps = steps;
      $dt.eaten = eaten;
      $dt.status = status;
      return $dt;
    }
    get is_S() { return this.$tag === 0; }
    get dtor_x() { return this.x; }
    get dtor_y() { return this.y; }
    get dtor_rot() { return this.rot; }
    get dtor_lives() { return this.lives; }
    get dtor_steps() { return this.steps; }
    get dtor_eaten() { return this.eaten; }
    get dtor_status() { return this.status; }
    toString() {
      if (this.$tag === 0) {
        return "Ls20Level2.S.S" + "(" + _dafny.toString(this.x) + ", " + _dafny.toString(this.y) + ", " + _dafny.toString(this.rot) + ", " + _dafny.toString(this.lives) + ", " + _dafny.toString(this.steps) + ", " + _dafny.toString(this.eaten) + ", " + _dafny.toString(this.status) + ")";
      } else  {
        return "<unexpected>";
      }
    }
    equals(other) {
      if (this === other) {
        return true;
      } else if (this.$tag === 0) {
        return other.$tag === 0 && _dafny.areEqual(this.x, other.x) && _dafny.areEqual(this.y, other.y) && _dafny.areEqual(this.rot, other.rot) && _dafny.areEqual(this.lives, other.lives) && _dafny.areEqual(this.steps, other.steps) && _dafny.areEqual(this.eaten, other.eaten) && _dafny.areEqual(this.status, other.status);
      } else  {
        return false; // unexpected
      }
    }
    static Default() {
      return Ls20Level2.S.create_S(_dafny.ZERO, _dafny.ZERO, _dafny.ZERO, _dafny.ZERO, _dafny.ZERO, _dafny.ZERO, Ls20Level2.Status.Default());
    }
    static Rtd() {
      return class {
        static get Default() {
          return S.Default();
        }
      };
    }
  }
  return $module;
})(); // end of module Ls20Level2
let _module = (function() {
  let $module = {};

  return $module;
})(); // end of module _module

module.exports = { Ls20Level2, _dafny };
